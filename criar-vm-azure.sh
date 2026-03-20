#!/bin/bash
# ============================================================
# Criar VM no Azure para JurisGen AI
# ============================================================
# Pré-requisito: Azure CLI instalado e logado (az login)
# ============================================================

RESOURCE_GROUP="rg-jurisgen"
VM_NAME="vm-jurisgen"
LOCATION="brazilsouth"
VM_SIZE="Standard_B2s"  # 2 vCPU, 4GB RAM - suficiente para o app
ADMIN_USER="jurisgen"

echo "Criando Resource Group..."
az group create --name $RESOURCE_GROUP --location $LOCATION

echo "Criando VM Ubuntu 22.04..."
az vm create \
  --resource-group $RESOURCE_GROUP \
  --name $VM_NAME \
  --image Ubuntu2204 \
  --size $VM_SIZE \
  --admin-username $ADMIN_USER \
  --generate-ssh-keys \
  --public-ip-sku Standard \
  --nsg-rule SSH

echo "Abrindo portas 80 (HTTP) e 443 (HTTPS)..."
az vm open-port --resource-group $RESOURCE_GROUP --name $VM_NAME --port 80 --priority 1001
az vm open-port --resource-group $RESOURCE_GROUP --name $VM_NAME --port 443 --priority 1002

# Pegar IP público
PUBLIC_IP=$(az vm show -d --resource-group $RESOURCE_GROUP --name $VM_NAME --query publicIps -o tsv)

echo ""
echo "=========================================="
echo "  VM criada com sucesso!"
echo "=========================================="
echo ""
echo "IP Público: $PUBLIC_IP"
echo ""
echo "PRÓXIMOS PASSOS:"
echo ""
echo "1. Conecte na VM:"
echo "   ssh $ADMIN_USER@$PUBLIC_IP"
echo ""
echo "2. Copie os arquivos do projeto para a VM:"
echo "   scp -r ./backend ./frontend ./deploy.sh $ADMIN_USER@$PUBLIC_IP:~/jurisgen/"
echo ""
echo "3. Na VM, execute o deploy:"
echo "   cd ~/jurisgen && bash deploy.sh"
echo ""
echo "4. Faça login no Claude CLI na VM:"
echo "   claude login"
echo ""
echo "5. Acesse: http://$PUBLIC_IP"
echo ""
