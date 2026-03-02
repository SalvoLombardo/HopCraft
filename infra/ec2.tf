# AMI: Amazon Linux 2023 (latest) per eu-south-1
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_key_pair" "hopcraft" {
  key_name   = "hopcraft-key"
  public_key = var.ssh_public_key
}

resource "aws_instance" "hopcraft" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.hopcraft.key_name
  vpc_security_group_ids = [aws_security_group.hopcraft.id]

  # Volume root: 20 GB gp3 (free tier: fino a 30 GB)
  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    delete_on_termination = true
  }

  # ---------------------------------------------------------------------------
  # User data: installa Docker + Docker Compose al primo avvio
  # ---------------------------------------------------------------------------
  user_data = <<-EOF
    #!/bin/bash
    set -e

    # Update system
    dnf update -y

    # Install Docker e Docker Compose plugin (disponibili nei repo AL2023)
    dnf install -y docker docker-compose-plugin

    # Enable + start Docker
    systemctl enable docker
    systemctl start docker

    # Add ec2-user al gruppo docker (evita sudo per ogni comando)
    usermod -aG docker ec2-user

    # Crea directory applicazione
    mkdir -p /opt/hopcraft
    chown ec2-user:ec2-user /opt/hopcraft
  EOF

  tags = {
    Name = "hopcraft-backend"
  }
}
