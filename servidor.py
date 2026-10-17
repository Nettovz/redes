import os
import socket
import sys

import rdt

HOST = "0.0.0.0"  #permite que o cliente acesse o servidor por qualquer ip da maquina
DEFAULT_PORT = 5000  #porta padrao, caso nao for informada
DEFAULT_LOSS = 0.2  #taxa de perda de pacote, caso nao for informada
DEFAULT_CORRUPT = 0.1  #taxa de pacotes corrompidos, caso nao for informada
DEFAULT_TIMER = 0.3  #temporizador padrao, caso nao for informado
STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "servidor_storage")  #pasta onde ficam os arquivos recebidos


def main():
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT  #primeiro argumento (opcional): porta
    loss = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LOSS  #segundo argumento (opcional): taxa de perda
    corrupt = float(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_CORRUPT  #terceiro argumento (opcional): taxa de corrupcao
    timeout = float(sys.argv[4]) if len(sys.argv) > 4 else DEFAULT_TIMER  #quarto argumento (opcional): temporizador

    rdt.set_channel(loss, corrupt, timeout)  #configura o canal simulado no rdt.py

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  #AF_INET = IPv4, SOCK_DGRAM = UDP
    sock.bind((HOST, porta))  #associa o socket ao ip da maquina + porta
    print(f"[SERVIDOR] Executando em {HOST}:{porta} "
          f"(perda={loss:.0%}, corrupção={corrupt:.0%}, timeout={timeout}s)")
    print(f"[SERVIDOR] Arquivos serão salvos em {STORAGE_DIR}")

    while True:  #loop do servidor, roda ate o Ctrl+C
        try:
            print("\n[SERVIDOR] Aguardando cliente...")
            filename, data, client_addr = rdt.recv_bytes(sock, "[SERVIDOR][RECEBE]", first_timeout=None)  #recebe com RDT 3.0
            stored_name = f"servidor_{filename}"  #prefixo servidor_
            stored_path = rdt.save_bytes(STORAGE_DIR, stored_name, data)  #grava em servidor_storage/
            print(f"[SERVIDOR] Arquivo salvo em disco: {stored_path}")

            print("[SERVIDOR] Devolvendo arquivo ao cliente...")
            rdt.send_bytes(sock, client_addr, stored_name, data, "[SERVIDOR][ENVIA]")  #devolve o arquivo com RDT 3.0
            print("[SERVIDOR] Transferência completa.")
        except KeyboardInterrupt:  #Ctrl+C
            print("\n[SERVIDOR] Encerrando.")
            break
        except (socket.timeout, ConnectionError) as e:  #transferencia falhou, aborta e volta a escutar
            print(f"[SERVIDOR][ERRO] Transferência abortada: {e}")
        except Exception as e:  #qualquer outro erro nao derruba o servidor
            print(f"[SERVIDOR][ERRO] {e}")


if __name__ == "__main__":
    main()