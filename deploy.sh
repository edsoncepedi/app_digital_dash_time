#!/bin/bash

# =========================
# CONFIGURAÇÕES
# =========================
CONTAINER_NAME="servidor_flask_digi"
IMAGE_NAME="app_digital_dash_time"
IMAGE_TAG="latest"
PORT_HOST=8000
PORT_CONTAINER=8000

# =========================
# PARAR CONTAINER (SE EXISTIR)
# =========================
if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    echo "🛑 Parando container $CONTAINER_NAME..."
    docker stop $CONTAINER_NAME
fi

# =========================
# REMOVER CONTAINER (SE EXISTIR)
# =========================
if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    echo "🗑️ Removendo container $CONTAINER_NAME..."
    docker rm $CONTAINER_NAME
fi

# =========================
# REMOVER IMAGEM (SE EXISTIR)
# =========================
if [ "$(docker images -q $IMAGE_NAME:$IMAGE_TAG)" ]; then
    echo "🗑️ Removendo imagem $IMAGE_NAME:$IMAGE_TAG..."
    docker rmi $IMAGE_NAME:$IMAGE_TAG
fi

# =========================
# BUILD DA NOVA IMAGEM
# =========================
echo "🔨 Buildando nova imagem..."
docker build -t $IMAGE_NAME:$IMAGE_TAG .

if [ $? -ne 0 ]; then
    echo "❌ Erro no build da imagem. Abortando."
    exit 1
fi

# =========================
# SUBIR NOVO CONTAINER
# =========================
echo "🚀 Subindo novo container..."

docker run -d --restart always \
   -p $PORT_HOST:$PORT_CONTAINER \
   -v $(pwd):/app \
   --log-driver json-file \
   --log-opt max-size=10m \
   --log-opt max-file=5 \
   --name $CONTAINER_NAME \
   $IMAGE_NAME:$IMAGE_TAG

echo "✅ Deploy concluído com sucesso!"
