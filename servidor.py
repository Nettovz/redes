import socket 
import sys
import os
from udp_protocol import receive_bytes, save_bytes, send_bytes

HOST = "0.0.0.0" #permite que o cliente possa acessar o servidor (receber dados) por qualquer ip dessa maquina
DEFAULT_PORT = 5000  # porta padrão utilizada pelo servidor para receber os dados

STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "servidor_storage")  # calcula e guarda o caminho da pasta (ao lado de servidor.py); a pasta em si só é criada depois, em save_bytes() no arquivo udp protocol
def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT #definicao da porta, caso o comando do terminal nao tiver a porta, usaremos a porta 500
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, port)) #associacao do host (qualquer ip do pc) + porta 
    sock.settimeout(10)  # evita travar para sempre se um pacote se perder
    print(f"executando o servidor em [{HOST}:{port}]")
    print(f"Os arquivos serão salvos em {STORAGE_DIR}")

    while True: #loop de funcionamento do servidor, sempre executa ate o comando do  "ctrl + c" 

        try: #receber o arquivo do cliente
            filename, data, client_addr = receive_bytes(sock, log_prefix = "[SERVIDOR][RECEBE]") #funcao feita no udp_protocol
            stored_name = f"servidor_{filename}"
            stored_path = save_bytes(STORAGE_DIR, stored_name, data)  #funcao feita no udp_protocol

            print(f"[SERVIDOR] Arquivo salvo em disco: {stored_path}")  # log confirmando onde o arquivo foi salvo
 
            # 3. Devolve o arquivo armazenado ao cliente, para confirmar o recebimento
            send_bytes(sock, client_addr, filename, data, log_prefix="[SERVIDOR][ENVIA]")  # reenvia o mesmo conteúdo de volta pro endereço do cliente que mandou

        except KeyboardInterrupt:               # se o usuário apertar Ctrl+C no terminal do servidor
            print("\n[SERVIDOR] Encerrando.")   # log de encerramento limpo
            break                                # sai do loop infinito e o programa termina
        except Exception as e:                  # qualquer outro erro inesperado durante uma transferência (ex: pacote corrompido)
            print(f"[SERVIDOR][ERRO] {e}")      # loga o erro, mas NÃO derruba o servidor — volta pro início do while e continua escutando
 
 
if __name__ == "__main__":  # só executa main() se este arquivo for rodado diretamente (python servidor.py), não se for importado
    main()
 

