# ===== IAM ROLE FOR GLUE =====
# Glue needs permission to read S3 and write to the Data Catalog
resource "aws_iam_role" "glue_role" {
  name = "glue-crawler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# AWS managed policy that gives Glue basic permissions
resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Additional policy to read from our processed bucket
resource "aws_iam_policy" "glue_s3_policy" {
  name = "glue-s3-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadProcessedBucket"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.processed_data.arn,
          "${aws_s3_bucket.processed_data.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "glue_s3_attach" {
  role       = aws_iam_role.glue_role.name
  policy_arn = aws_iam_policy.glue_s3_policy.arn
}

# ===== GLUE DATABASE =====
# A logical container for your tables in the Data Catalog
# Think of it like a database in SQL — it groups related tables together
resource "aws_glue_catalog_database" "weather_db" {
  name        = "weather_analytics_db"
  description = "Database for weather pipeline analytics"
}

# ===== GLUE CRAWLER =====
# Scans your S3 bucket and automatically detects the schema
# Creates/updates a table in the Data Catalog
resource "aws_glue_crawler" "weather_crawler" {
  name          = "weather-data-crawler"
  role          = aws_iam_role.glue_role.arn
  database_name = aws_glue_catalog_database.weather_db.name
  description   = "Crawls processed weather data and updates the Data Catalog"

  # Where to scan — our processed data folder
  s3_target {
    path = "s3://${aws_s3_bucket.processed_data.bucket}/processed/"
  }

  # How often to run — on demand only (we trigger it manually or via schedule)
  schedule = "cron(0 */6 * * ? *)"

  schema_change_policy {
    update_behavior = "LOG"
    delete_behavior = "LOG"
  }

  # Recrawl only new/changed files — much faster and cheaper
  recrawl_policy {
    recrawl_behavior = "CRAWL_NEW_FOLDERS_ONLY"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
      Tables     = { AddOrUpdateBehavior = "MergeNewColumns" }
    }
  })
}