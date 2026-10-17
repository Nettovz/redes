import os
import socket
import sys

import rdt

DEFAULT_HOST = "127.0.0.1" #ip padrao, caso o cliente nao colocar
DEFAULT_PORT = 5000 #porta padrao, caso o cliente nao colocar
STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cliente_storage") #criar a pasta que fica o arquivo enviado
DEFAULT_LOSS = 0.2 #definicao de taxa de perda de pacote para teste caso o cliente nao fornecer
DEFAULT_CORRUPT = 0.1 #definicao de taxa de pacotes que sao corrompidos caso o cliente nao fornecer
DEFAULT_TIMER = 0.3 #definicao do temporizador inicial

def main():

    if len(sys.argv) < 2: #debug
        print("Uso: python cliente.py arquivo [host] [porta] [loss] [corrupt] [timeout]")
        sys.exit(1)

    arquivo = sys.argv[1] # primeiro argumento do terminal: caminho do arquivo a ser enviado
    host = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_HOST    # segundo argumento (opcional): host do servidor
    porta = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_PORT  # terceiro argumento (opcional): porta do servidor
    loss = float(sys.argv[4]) if len(sys.argv) > 4 else DEFAULT_LOSS  # quarto argumento (opcional): taxa de perda
    corrupt = float(sys.argv[5]) if len(sys.argv) > 5 else DEFAULT_CORRUPT  # quinto argumento (opcional):taxa de pacotes corrompidos
    timeout = float(sys.argv[6]) if len(sys.argv) > 6 else DEFAULT_TIMER  # sexto argumento (opcional): temporizador
    
    rdt.set_channel(loss, corrupt, timeout) #funcao criada no rdt.py para configurar o canal de comunicação simulado usado pelo protocolo RDT

  
    if not os.path.isfile(arquivo): #debug caso nao encontrar o arquivo
        print(f"[CLIENTE][ERRO] Arquivo não encontrado: {arquivo}")
        sys.exit(1)

    server_addr = (host, porta) # monta a tupla (ip, porta) usada pelo socket como destino
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # cria o socket: AF_INET = IPv4, SOCK_DGRAM = UDP

    print(f"[CLIENTE] Servidor: {server_addr} (perda={loss:.0%}, "f"corrupção={corrupt:.0%}, timeout={timeout}s)")

    try:
        _, original = rdt.send_file(sock, server_addr, arquivo, "[CLIENTE][ENVIA]")  # lê o arquivo do disco e envia fragmentado ao servidor

        print("[CLIENTE] Aguardando devolução do arquivo pelo servidor...")
        returned_name, returned_data, _ = rdt.recv_bytes(sock, "[CLIENTE][RECEBE]", addr=server_addr, first_timeout=30, timeout=10) # Função que realiza a montagem dos pacotes usando bit alternado e tratamento de pacotes duplicados.

        local_name = f"cliente_{returned_name}"   # gera o nome local, prefixado (o nome recebido já vem com "servidor_" também)
        saved = rdt.save_bytes(STORAGE_DIR, local_name, returned_data) # grava a cópia devolvida em disco, dentro de cliente_storage/
        print(f"[CLIENTE] Cópia devolvida salva em: {saved}")# log confirmando onde a cópia foi salva

          # Verificação simples de integridade
        if returned_data == original:  # compara byte a byte o que foi enviado com o que voltou
            print("[CLIENTE] Sucesso: conteúdo devolvido é idêntico ao enviado.") # tudo certo, a transferência foi íntegra
        else:
            print("[CLIENTE][AVISO] Conteúdo devolvido difere do original!") # algo se perdeu/corrompeu no caminho
            sys.exit(2)

    except (socket.timeout, ConnectionError) as e:  # Captura erros de timeout ou de conexão durante a transferência
        print(f"[CLIENTE][ERRO] Falha na transferência: {e}")
        sys.exit(1)
    finally:
        sock.close() #fecha socket


if __name__ == "__main__":
    main()
