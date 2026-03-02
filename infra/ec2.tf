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

  # Volume root: 30 GB gp3 (minimo richiesto dall'AMI AL2023 in eu-south-1; free tier copre fino a 30 GB)
  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = true
  }

  # ---------------------------------------------------------------------------
  # User data: installa Docker + Docker Compose al primo avvio
  # ---------------------------------------------------------------------------
  user_data = <<-EOF
    #!/bin/bash
    # Non usare set -e: dnf update può restituire exit code != 0 su warning non fatali

    # Update system (ignora errori non fatali)
    dnf update -y || true

    # Install Docker (dal repo AL2023 — non include il Compose plugin)
    dnf install -y docker

    # Enable + start Docker
    systemctl enable docker
    systemctl start docker

    # Add ec2-user al gruppo docker (evita sudo per ogni comando)
    usermod -aG docker ec2-user

    # Install Docker Compose V2 plugin da GitHub (non disponibile nei repo AL2023)
    DOCKER_CONFIG=/home/ec2-user/.docker
    mkdir -p $DOCKER_CONFIG/cli-plugins
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
         -o $DOCKER_CONFIG/cli-plugins/docker-compose
    chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
    chown -R ec2-user:ec2-user $DOCKER_CONFIG

    # Crea directory applicazione
    mkdir -p /opt/hopcraft
    chown ec2-user:ec2-user /opt/hopcraft

    # Segnale di completamento (visibile in /var/log/cloud-init-output.log)
    echo "=== user_data completed ==="
  EOF

  tags = {
    Name = "hopcraft-backend"
  }
}
