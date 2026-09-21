import socket  # biblioteca padrão pra criar sockets (aqui, um socket UDP)
import sys     # usado pra ler os argumentos da linha de comando (arquivo, host, porta)
import os      # usado pra montar caminhos e checar se o arquivo existe

from udp_protocol import send_file, receive_bytes, save_bytes  # importa as funções de protocolo já implementadas

DEFAULT_HOST = "127.0.0.1"  # host padrão do servidor, caso não seja informado (localhost)
DEFAULT_PORT = 5000          # porta padrão do servidor, caso não seja informada
STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cliente_storage")  # caminho absoluto de cliente_storage/

def main():
    if len(sys.argv) < 2:  # o único argumento obrigatório é o caminho do arquivo a enviar
        print("Uso: python cliente.py <caminho_do_arquivo> [host_servidor] [porta_servidor]")  # instrução de uso, se faltou argumento
        sys.exit(1)  

    filepath = sys.argv[1]                                      # primeiro argumento: caminho do arquivo a ser enviado
    host = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_HOST    # segundo argumento (opcional): host do servidor
    port = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_PORT  # terceiro argumento (opcional): porta do servidor

    if not os.path.isfile(filepath):  # confere se o caminho informado nao aponta pra um arquivo existente
        print(f"[CLIENTE][ERRO] Arquivo não encontrado: {filepath}")  # avisa o usuário se o arquivo não existe
        sys.exit(1)  # encerra o programa com código de erro

    server_addr = (host, port)                                # monta a tupla (ip, porta) usada pelo socket como destino
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # cria o socket: AF_INET = IPv4, SOCK_DGRAM = UDP
    sock.settimeout(10)  # evita ficar travado indefinidamente esperando resposta

    try:
        # 1. Envia o arquivo ao servidor
        filename, original_data = send_file(sock, server_addr, filepath, log_prefix="[CLIENTE][ENVIA]")  # lê o arquivo do disco e envia fragmentado ao servidor

        # 2. Aguarda a devolução do servidor (confirmação) e valida se o nome devolvido bate com o enviado
        returned_name, returned_data, _ = receive_bytes(sock, log_prefix="[CLIENTE][RECEBE]")  # bloqueia até o servidor remontar e devolver o arquivo

        if returned_name is None:
            print("[CLIENTE][ERRO] Servidor não devolveu o arquivo a tempo.")
            sys.exit(1)

        if os.path.basename(returned_name) != os.path.basename(filename):
            print(f"[CLIENTE][AVISO] Nome devolvido difere: {returned_name} != {filename}")

        # 3. Salva a cópia recebida com prefixo "cliente_"
        local_name = f"cliente_{returned_name}"                         # gera o nome local, prefixado (o nome recebido já vem com "servidor_" também)
        saved_path = save_bytes(STORAGE_DIR, local_name, returned_data)  # grava a cópia devolvida em disco, dentro de cliente_storage/
        print(f"[CLIENTE] Confirmação salva em: {saved_path}")          # log confirmando onde a cópia foi salva

        # 4. Verificação simples de integridade
        if returned_data == original_data:  # compara byte a byte o que foi enviado com o que voltou
            print("[CLIENTE] Sucesso: conteúdo devolvido é idêntico ao enviado.")  # tudo certo, a transferência foi íntegra
        else:
            print("[CLIENTE][AVISO] Conteúdo devolvido difere do original!")  # algo se perdeu/corrompeu no caminho

    except socket.timeout:  # se passar o tempo definido em sock.settimeout(10) sem resposta do servidor
        print("[CLIENTE][ERRO] Tempo esgotado aguardando resposta do servidor.")  # avisa o usuário que o servidor não respondeu a tempo
    finally:
        sock.close()  # fecha o socket de qualquer forma, com ou sem erro, liberando o recurso do sistema


if __name__ == "__main__":  # só executa main() se este arquivo for rodado diretamente (python cliente.py), não se for importado
    main()
