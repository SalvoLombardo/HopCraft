# Bucket S3 per il frontend React (file statici)
resource "aws_s3_bucket" "frontend" {
  bucket = var.frontend_bucket_name
}

# Blocca tutto l'accesso pubblico diretto — CloudFront accede via OAC (firma interna)
resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Origin Access Control: CloudFront firma le richieste a S3 con SigV4
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "hopcraft-frontend-oac"
  description                       = "OAC per bucket S3 frontend HopCraft"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Bucket policy: solo CloudFront può leggere gli oggetti
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontOAC"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.frontend.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.hopcraft.arn
          }
        }
      }
    ]
  })

  # Dependency esplicita: la policy richiede che la distribuzione esista
  depends_on = [aws_cloudfront_distribution.hopcraft]
}
