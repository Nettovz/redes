import json    # serializa/desserializa o pacote de metadados (nome, tamanho, nuumer de pedaços)
import struct  # empacota o número de sequência como 4 bytes binários (inteiro de rede)
import math    # usa math.ceil pra calcular quantos pacotes são necessários (arredonda pra cima)

PACKET_SIZE = 1024                            # limite máximo de bytes por datagrama UDP, exigido pelo enunciado
HEADER_DATA_SIZE = 1 + 4                      # cabeçalho de um pacote de dados: 1 byte de tipo (D) + 4 bytes de sequência
CHUNK_SIZE = PACKET_SIZE - HEADER_DATA_SIZE   # sobra pra dados de verdade em cada pacote: 1024 - 5 = 1019 bytes

def send_bytes(sock, addr, filename, data,log_prefix = "[ENVIO]"): #Vamos fragmentar o data e enviar via sock para addr
    filesize = len(data) #ver o tamanho do arquivo em  bytes
    total_pacotes = max(1, math.ceil(filesize/ CHUNK_SIZE)) #numero de pacotes que vamos partir o dado, no minimo 1

    meta = json.dumps({                # monta um dicionário Python com as infos que o outro lado precisa saber antes de receber os dados
        "filename": filename,          # nome do arquivo, pra saber como salvar do outro lado
        "filesize": filesize,          # tamanho total em bytes, só informativo/log
        "total_chunks": total_pacotes,  # quantidade de pacotes de dados que virão em seguida
    }).encode("utf-8")                 # converte o JSON (string) para bytes, pra poder concatenar com o marcador b"M"
    sock.sendto(b"M" + meta, addr)     # envia o pacote de metadados: 1 byte 'M' (marca o tipo) + o JSON em bytes
    print(f"{log_prefix} Metadados enviados: {filename} ({filesize} bytes, {total_pacotes} pacotes) -> {addr}")  # log do envio dos metadados

    for seq in range(total_pacotes):                  # percorre cada pedaço do arquivo, numerado de 0 até total_pacotes-1
        start = seq * CHUNK_SIZE                      # posição inicial (em bytes) desse pedaço dentro de `data`
        chunk = data[start:start + CHUNK_SIZE]        # fatia até CHUNK_SIZE bytes a partir de `start` (o Python trunca sozinho no final)
        header = b"D" + struct.pack("!I", seq)        # cabeçalho do pacote de dados: 1 byte 'D' + número de sequência em 4 bytes big-endian
        sock.sendto(header + chunk, addr)             # envia o pacote UDP: cabeçalho + pedaço de dados, pro endereço de destino

    print(f"{log_prefix} Envio de '{filename}' concluído ({total_pacotes} pacotes).") #p falar que enviou
    return filename, data


def send_file(sock, addr, filepath ,log_prefix = "[ENVIO]"): #Lê um arquivo do disco e envia via send_bytes, usando o nome base do arquivo.
    import os
    filename = os.path.basename(filepath) #extrai o nome do arquivo
    with open(filepath, "rb") as f: #abre o arquivo em modo binário 
        data = f.read() #Leia todo o conteúdo do arquivo e coloque os bytes na variável data 
    send_bytes(sock, addr, filename, data, log_prefix = log_prefix) #envia pra send_bytes, já com nome+conteúdo em mãos
    return filename, data


def receive_bytes(sock, log_prefix="[RECEBIMENTO]"): #Receber os pedaços que vieram pela rede e reconstruir o arquivo original.
    packet, addr = sock.recvfrom(PACKET_SIZE + 64)

    while packet[0:1] != b"M":
        packet, addr = sock.recvfrom(PACKET_SIZE + 64)

    meta = json.loads(packet[1:].decode("utf-8"))   # remove o byte 'M' (packet[1:]), decodifica de bytes pra string e faz o parse do JSON
    filename = meta["filename"]                     # extrai o nome do arquivo do dicionário de metadados
    filesize = meta["filesize"]                     # extrai o tamanho total esperado, em bytes
    total_chunks = meta["total_chunks"]              # extrai quantos pacotes de dados devem chegar

    print(f"{log_prefix} Metadados recebidos de {addr}: {filename} ({filesize} bytes, {total_chunks} pacotes)")  # log dos metadados recebidos

    chunks = {}                                      # dicionário {número_de_sequência: bytes_do_pedaço}, pra remontar na ordem certa depois
    while len(chunks) < total_chunks:                # continua recebendo até já ter todos os pedaços esperados
        packet, sender = sock.recvfrom(PACKET_SIZE + 64)  # espera o próximo pacote UDP chegar
        if sender != addr:                           # se veio de outro endereço (outro cliente concorrente, por exemplo)
            continue                                  # ignora esse pacote e volta a esperar — não pertence a esta transferência
        if packet[0:1] != b"D":                       # se o primeiro byte não for 'D', não é um pacote de dados válido
            continue                                  # ignora e continua esperando
        seq = struct.unpack("!I", packet[1:5])[0]     # desempacota os 4 bytes (posições 1 a 4) de volta pra um inteiro: o número de sequência
        chunks[seq] = packet[5:]                       # guarda o restante do pacote (a partir do byte 5) como o conteúdo desse pedaço

    data = b"".join(chunks[i] for i in range(total_chunks))  # concatena os pedaços na ordem certa (0, 1, 2, ...), remontando o arquivo original
    if len(data) != filesize:                     # confere se o total remontado bate com o tamanho informado nos metadados
        print(f"{log_prefix} AVISO: tamanho remontado ({len(data)}) difere do esperado ({filesize}).")  # loga aviso de possível perda/corrupção
    else:
        print(f"{log_prefix} '{filename}' remontado com sucesso ({len(data)} bytes).")  # log confirmando a remontagem completa
    return filename, data, addr          


def save_bytes(save_dir, filename, data):
    import os                                # importado aqui dentro só porque só é usado nesta função
    os.makedirs(save_dir, exist_ok=True)     # cria a pasta de destino se ela ainda não existir (não dá erro se já existir)
    path = os.path.join(save_dir, filename)  # monta o caminho completo do arquivo a ser salvo (pasta + nome)
    with open(path, "wb") as f:               # abre (ou cria) o arquivo em modo binário de escrita ("wb")
        f.write(data)                         # grava todos os bytes recebidos no arquivo
    return path                               # devolve o caminho completo, útil pra log/confirmação
