output "ec2_public_ip" {
  description = "IP pubblico dell'EC2 — da aggiornare nel secret GitHub EC2_HOST"
  value       = aws_instance.hopcraft.public_ip
}

output "ec2_public_dns" {
  description = "DNS pubblico dell'EC2"
  value       = aws_instance.hopcraft.public_dns
}

output "cloudfront_url" {
  description = "URL dell'app (HTTPS, no dominio richiesto) — da condividere nel portfolio"
  value       = "https://${aws_cloudfront_distribution.hopcraft.domain_name}"
}

output "cloudfront_distribution_id" {
  description = "ID della distribuzione CloudFront — da aggiungere al secret GitHub CLOUDFRONT_DISTRIBUTION_ID"
  value       = aws_cloudfront_distribution.hopcraft.id
}

output "s3_bucket_name" {
  description = "Nome del bucket S3 frontend — da aggiungere al secret GitHub S3_BUCKET_NAME"
  value       = aws_s3_bucket.frontend.bucket
}
