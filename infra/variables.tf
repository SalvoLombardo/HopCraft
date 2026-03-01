variable "aws_region" {
  description = "AWS region (eu-south-1 = Milano, eu-west-1 = Irlanda)"
  type        = string
  default     = "eu-south-1"
}

variable "instance_type" {
  description = "EC2 instance type — t3.micro è free tier eligible (750h/mese)"
  type        = string
  default     = "t3.micro"
}

variable "frontend_bucket_name" {
  description = "Nome del bucket S3 per il frontend React (deve essere globalmente unico, es. hopcraft-frontend-tuonome)"
  type        = string
}

variable "ssh_public_key" {
  description = "Contenuto della chiave pubblica SSH per accesso EC2 (es. output di `cat ~/.ssh/hopcraft.pub`)"
  type        = string
  sensitive   = true
}

variable "my_ip" {
  description = "Il tuo IP per accesso SSH (formato: x.x.x.x/32). Usa 0.0.0.0/0 solo per test."
  type        = string
  default     = "0.0.0.0/0"
}
