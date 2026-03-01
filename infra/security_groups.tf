resource "aws_security_group" "hopcraft" {
  name        = "hopcraft-sg"
  description = "Security group per EC2 HopCraft"

  # HTTP dalla CloudFront (porta 80 → Nginx → FastAPI)
  # Nota: CloudFront usa IP variabili — in produzione si può usare il managed prefix list
  # aws_ec2_managed_prefix_list "cloudfront" ma richiede lookup extra.
  # Per semplicità, 0.0.0.0/0 su 80 è accettabile: il backend non serve dati sensibili.
  ingress {
    description = "HTTP (CloudFront → Nginx)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # SSH — limitato al tuo IP (o 0.0.0.0/0 se non sai l'IP)
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }

  # Tutto il traffico in uscita (necessario per pull immagini GHCR, chiamate API esterne)
  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "hopcraft-sg"
  }
}
