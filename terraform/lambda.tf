# ===== IAM ROLE FOR LAMBDA =====
resource "aws_iam_role" "lambda_pipeline_role" {
  name = "lambda-pipeline-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# ===== IAM POLICY =====
# Least privilege — only what Lambda actually needs
resource "aws_iam_policy" "lambda_pipeline_policy" {
  name = "lambda-pipeline-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Read from raw bucket
        Sid    = "ReadRawBucket"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.raw_data.arn,
          "${aws_s3_bucket.raw_data.arn}/*"
        ]
      },
      {
        # Write to processed bucket
        Sid    = "WriteProcessedBucket"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.processed_data.arn,
          "${aws_s3_bucket.processed_data.arn}/*"
        ]
      },
      {
        # Write logs to CloudWatch
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_pipeline_attach" {
  role       = aws_iam_role.lambda_pipeline_role.name
  policy_arn = aws_iam_policy.lambda_pipeline_policy.arn
}

# ===== PACKAGE LAMBDA CODE =====
# Zips the python file automatically — no manual zip needed!
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "../lambda/process_data.py"
  output_path = "../lambda/process_data.zip"
}

# ===== LAMBDA FUNCTION =====
resource "aws_lambda_function" "pipeline" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "weather-data-processor"
  role             = aws_iam_role.lambda_pipeline_role.arn
  handler          = "process_data.lambda_handler"
  runtime          = "python3.12"
  timeout          = 60
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      LOG_LEVEL = "INFO"
    }
  }
}

# ===== S3 EVENT TRIGGER =====
# Tells S3 to invoke Lambda every time a file is uploaded
resource "aws_s3_bucket_notification" "raw_data_trigger" {
  bucket = aws_s3_bucket.raw_data.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.pipeline.arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".csv"
  }

  depends_on = [aws_lambda_permission.s3_invoke]
}

# ===== PERMISSION FOR S3 TO INVOKE LAMBDA =====
resource "aws_lambda_permission" "s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pipeline.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.raw_data.arn
}