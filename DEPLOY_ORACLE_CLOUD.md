# Roteiro Passo a Passo: Publicação na Oracle Cloud (Always Free) na Porta 80

Este guia cobre desde a criação da nova instância **Always Free** no Console da Oracle Cloud (OCI) até a publicação da ferramenta `mestrado_poc` respondendo diretamente em **`http://<IP_PUBLICO>`** (Porta 80).

---

## Parte 1: Criar a Instância Always Free no Console da Oracle

O plano **Always Free** da Oracle permite ter **até 2 instâncias `VM.Standard.E2.1.Micro` (AMD)** gratuitamente (ou instâncias ARM `VM.Standard.A1.Flex` até 4 OCPUs / 24 GB RAM). Como você já possui a `kratos`, ainda tem direito à segunda `VM.Standard.E2.1.Micro` sem custo.

1. Acesse o Console da Oracle Cloud: **Compute** → **Instances** → **Create instance**.
2. **Name:** `mestrado-poc` (ou o nome de sua preferência).
3. **Placement:** Mantenha o mesmo Availability Domain (`AD-1`).
4. **Image and shape (Importante):**
   - Clique em **Change image** e selecione **Canonical Ubuntu** → **Ubuntu 24.04 Minimal/Server** ou **Ubuntu 22.04** (sempre marcados como *Always Free-eligible*).
   - Em **Shape**, mantenha `VM.Standard.E2.1.Micro` (1 OCPU, 1 GB RAM - *Always Free-eligible*).
5. **Primary VNIC information (Rede):**
   - Selecione a mesma **VCN** e **Subnet pública** onde está sua instância `kratos` (assim ela já nasce com Internet Gateway configurado).
   - Certifique-se de que **Assign a public IPv4 address** está marcado.
6. **Add SSH keys:**
   - Baixe o par de chaves (**Save private key**) ou envie sua chave pública `.pub` habitual.
7. Clique em **Create** e anote o **Public IP address** gerado (ex.: `164.152.XX.XX`).

---

## Parte 2: Liberar a Porta 80 (HTTP) no Painel da Oracle Cloud (VCN)

Por padrão, a rede virtual da Oracle bloqueia tudo exceto SSH (porta 22). Para liberar a porta 80:

1. Na página da sua nova instância no Console da Oracle, clique no link da **Subnet** (em *Primary VNIC*).
2. Dentro da Subnet, clique na **Default Security List for <sua-vcn>**.
3. Em **Ingress Rules** (Regras de Entrada), clique em **Add Ingress Rules** e preencha:
   - **Source Type:** `CIDR`
   - **Source CIDR:** `0.0.0.0/0`
   - **IP Protocol:** `TCP`
   - **Destination Port Range:** `80`
   - **Description:** `HTTP Mestrado PoC`
4. Clique em **Add Ingress Rules**.

---

## Parte 3: Enviar o Código da sua Máquina Windows para a Nova VPS

No PowerShell da sua máquina (`d:\mestrado_poc`), envie a pasta do projeto para a nova VM via `scp` (substitua `<CAMINHO_CHAVE.key>` e `<IP_PUBLICO>`):

```powershell
# Compacta ou envia direto os arquivos essenciais para a pasta /home/ubuntu/mestrado_poc
ssh -i <CAMINHO_CHAVE.key> ubuntu@<IP_PUBLICO> "mkdir -p ~/mestrado_poc"
scp -i <CAMINHO_CHAVE.key> -r d:\mestrado_poc\app.py d:\mestrado_poc\requirements.txt d:\mestrado_poc\README.md d:\mestrado_poc\src d:\mestrado_poc\dados d:\mestrado_poc\deploy ubuntu@<IP_PUBLICO>:~/mestrado_poc/
```

*(Alternativa: se você subir o repositório para o GitHub, basta conectar via SSH na VM e rodar `git clone <URL_DO_REPO> ~/mestrado_poc`).*

---

## Parte 4: Executar o Script de Instalação Automatizada na VPS

Conecte-se à nova VPS via SSH e execute o script [`deploy/setup_oracle_vps.sh`](file:///d:/mestrado_poc/deploy/setup_oracle_vps.sh) que já preparamos no repositório:

```bash
ssh -i <CAMINHO_CHAVE.key> ubuntu@<IP_PUBLICO>

cd ~/mestrado_poc
sed -i 's/\r$//' deploy/setup_oracle_vps.sh
sudo bash deploy/setup_oracle_vps.sh
```

### O que esse script faz sozinho por você?
1. **Cria 2 GB de Swap em disco:** Garante que a VM de 1 GB de RAM nunca trave por falta de memória.
2. **Instala pacotes base:** Python 3, `venv`, `nginx` e o próprio `swi-prolog` nativo do Linux.
3. **Configura a aplicação em `/opt/mestrado_poc`:** Cria o ambiente virtual `.venv` e instala todas as bibliotecas do `requirements.txt`.
4. **Cria o serviço `systemd` (`mestrado-poc.service`):** Faz a aplicação iniciar sozinha quando a VM ligar e reiniciar automaticamente em caso de falha.
5. **Configura o Nginx na Porta 80:** Redireciona todo o tráfego de `http://<IP_PUBLICO>` (porta 80) para o Streamlit interno (`127.0.0.1:8501`) com suporte completo a WebSockets (`/_stcore/stream`).
6. **Abre a Porta 80 no `iptables` do Ubuntu da Oracle:** Remove o bloqueio padrão de fábrica das imagens Ubuntu da Oracle Cloud e salva a regra permanentemente com `netfilter-persistent`.

---

## Parte 5: (Opcional) Configurar sua `GEMINI_API_KEY` no Servidor

Se quiser deixar uma chave padrão configurada no servidor (para não precisar digitar na barra lateral da interface):

```bash
sudo bash -c 'echo "GEMINI_API_KEY=sua_chave_aqui" > /opt/mestrado_poc/.env'
sudo chmod 600 /opt/mestrado_poc/.env
sudo systemctl restart mestrado-poc
```

---

## Comandos Úteis de Manutenção na VPS

- **Ver logs da aplicação em tempo real:**
  ```bash
  sudo journalctl -u mestrado-poc -f
  ```
- **Reiniciar a aplicação após atualizar arquivos:**
  ```bash
  sudo bash ~/mestrado_poc/deploy/setup_oracle_vps.sh
  ```
