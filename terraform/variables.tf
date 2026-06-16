variable "aws_region"{
    description = "AWS region"
    type        = string
    default     = "us-east-1"
}

variable "raw_bucket_name" {
    description = "S3 bucket for incoming raw data"
    type        = string
    default     = olympus-raw-weather-data"
}

variable "processed_bucket_name" {
    description = "S3 bucket for cleaned data"
    type        = string
    default     = "olympus-processed-weather-data"
}
variable "alert_email" {
    description = "Email address to receive SNS failure alerts"
    type        = string
}