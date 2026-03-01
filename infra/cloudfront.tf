resource "aws_cloudfront_distribution" "hopcraft" {
  enabled             = true
  default_root_object = "index.html"
  comment             = "HopCraft — SPA + API proxy"
  price_class         = "PriceClass_100" # Solo Europa + Nord America (free tier compatibile)

  # ---------------------------------------------------------------------------
  # Origin 1: S3 (React SPA)
  # ---------------------------------------------------------------------------
  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "S3-hopcraft-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # ---------------------------------------------------------------------------
  # Origin 2: EC2 (FastAPI via Nginx, HTTP)
  # ---------------------------------------------------------------------------
  origin {
    domain_name = aws_instance.hopcraft.public_dns
    origin_id   = "EC2-hopcraft-backend"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only" # Nginx su EC2 parla HTTP (TLS termina a CF)
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # ---------------------------------------------------------------------------
  # Behavior /api/* → EC2 (no cache, forward tutto)
  # ---------------------------------------------------------------------------
  ordered_cache_behavior {
    path_pattern           = "/api/*"
    target_origin_id       = "EC2-hopcraft-backend"
    viewer_protocol_policy = "redirect-to-https"

    allowed_methods = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods  = ["GET", "HEAD"]

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Content-Type", "Accept", "Origin"]
      cookies {
        forward = "none"
      }
    }

    # Nessun caching per le API
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0

    compress = true
  }

  # ---------------------------------------------------------------------------
  # Behavior default /* → S3 (React SPA, con cache aggressiva)
  # ---------------------------------------------------------------------------
  default_cache_behavior {
    target_origin_id       = "S3-hopcraft-frontend"
    viewer_protocol_policy = "redirect-to-https"

    allowed_methods = ["GET", "HEAD", "OPTIONS"]
    cached_methods  = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 86400    # 1 giorno per file HTML
    max_ttl     = 31536000 # 1 anno per asset con hash nel nome

    compress = true
  }

  # ---------------------------------------------------------------------------
  # SPA fallback: 403/404 da S3 → serve index.html (React Router funziona)
  # ---------------------------------------------------------------------------
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Certificato CloudFront default (*.cloudfront.net) — non richiede dominio
  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name = "hopcraft-cdn"
  }
}
