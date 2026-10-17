"""RDT 3.0 (stop-and-wait) em camada de aplicação sobre socket UDP.

Formato do pacote (<= 1024 bytes):
    tipo (1 byte: M, D, A ou N) | seq (1 byte: 0 ou 1) | payload | CRC32 (4 bytes)
    M = metadados, D = dados, A = ACK, N = NAK
"""
import json
import math
import os
import random
import socket
import struct
import time
import zlib

PACKET_SIZE = 1024                       # limite de bytes por datagrama
HEADER_SIZE = 1 + 1 + 4                  # tipo + seq + CRC32
CHUNK_SIZE = PACKET_SIZE - HEADER_SIZE   # bytes úteis por pacote (1018)
MAX_RETRIES = 30                         # tentativas por pacote antes de desistir

# Parâmetros do canal (ajustáveis por set_channel)
TIMEOUT = 0.3        # segundos esperando o ACK
LOSS_PROB = 0.3      # probabilidade de perder cada pacote enviado (dados e ACK/NAK)
CORRUPT_PROB = 0.1   # probabilidade de corromper cada pacote enviado
LINGER = 5 * TIMEOUT # tempo extra reenviando ACK após o último pacote


def set_channel(loss=None, corrupt=None, timeout=None): #muda os parâmetros do canal simulado, caso o cliente fornece las
    """Configura o gerador aleatório de perdas/corrupção e o timeout."""
    global LOSS_PROB, CORRUPT_PROB, TIMEOUT, LINGER
    if loss is not None:
        LOSS_PROB = loss
    if corrupt is not None:
        CORRUPT_PROB = corrupt
    if timeout is not None:
        TIMEOUT = timeout
        LINGER = 5 * timeout


def make_pkt(tipo, seq, payload=b""): #monta o pacote que vai pelo socket udp, ela junta o tipo, o numero de sequencia e o conteudo, e coloca no final um CRC32, um código que permite ao receptor detectar se algum byte foi alterado no caminho
    body = tipo + bytes([seq]) + payload
    return body + struct.pack("!I", zlib.crc32(body))


def parse_pkt(raw): #recebe os bytes crus que chegaram do socket, confere se estão íntegros e, se estiverem, separa o pacote em tipo, seq e payload,se algo estiver errado, devolve
    if len(raw) < HEADER_SIZE: # Um pacote válido nunca tem menos que 6
        return None
    body, crc = raw[:-4], struct.unpack("!I", raw[-4:])[0] #Separar o corpo e o CRC recebido
    if zlib.crc32(body) != crc: #Iguais: o conteúdo chegou como foi enviado. ou Diferentes: algum byte mudou no caminho. O pacote é considerado corrompido e devolve
        return None
    return body[0:1], body[1], body[2:] #Devolver as partes


def unreliable_send(sock, addr, pkt, log, desc): #simula um canal de rede ruim
    """decide por sorteio se o pacote:

se perde (nunca chega ao destino),
chega corrompido (com um byte alterado), ou
chega normal."""

    if random.random() < LOSS_PROB: #Sorteio da perda
        print(f"{log} [PERDA SIMULADA] {desc}")
        return
    if random.random() < CORRUPT_PROB: #Sorteio da corrupção
        pkt = bytes([pkt[0] ^ 0xFF]) + pkt[1:] #corrompe o pacote
        print(f"{log} [CORRUPÇÃO SIMULADA] {desc}")
    sock.sendto(pkt, addr) #Envia de verdade, se não houve perda, o pacote vai. Se houve corrupção, vai alterado, se nenhum dos dois sorteios acionou, vai intacto


def rdt_send(sock, addr, tipo, seq, payload, log):
    """Envia um pacote e só retorna quando receber o ACK correspondente."""
    pkt = make_pkt(tipo, seq, payload)  #monta o pacote uma vez só (tipo+seq+payload+CRC), as retransmissões reenviam esse mesmo
    t = tipo.decode()  #converte b"D" em "D" pra aparecer bonito no log
    for tentativa in range(1, MAX_RETRIES + 1):  #até 30 tentativas, se passar disso desiste
        if tentativa == 1:  #primeira vez é um envio normal
            print(f"{log} Enviando {t} seq={seq} ({len(payload)} bytes)")
        else:  #da segunda em diante é retransmissão
            print(f"{log} RETRANSMITINDO {t} seq={seq} (tentativa {tentativa})")
        unreliable_send(sock, addr, pkt, log, f"{t} seq={seq}")  #manda pelo canal ruim, pode se perder ou ser corrompido
        deadline = time.time() + TIMEOUT  #liga o timer: instante limite pra esperar o ACK
        while True:  #fica ouvindo até: chegar o ACK certo, estourar o timer ou chegar um NAK
            restante = deadline - time.time()  #quanto tempo ainda sobra do timer
            if restante <= 0:  #o tempo acabou
                print(f"{log} TIMEOUT aguardando ACK seq={seq}")
                break  #sai do while e vai pra próxima tentativa (retransmite)
            sock.settimeout(restante)  #o recvfrom espera só o tempo que sobra, não um valor fixo
            try:
                raw, src = sock.recvfrom(PACKET_SIZE + 64)  #espera chegar alguma resposta
            except socket.timeout:  #nada chegou até o fim do timer
                print(f"{log} TIMEOUT aguardando ACK seq={seq}")
                break  #também vai retransmitir
            if src != addr:  #veio de outro endereço, não é a resposta que a gente espera
                continue
            p = parse_pkt(raw)  #confere o CRC e separa o pacote
            if p is None:  #resposta corrompida, não dá pra confiar nela
                print(f"{log} Resposta corrompida, ignorando")
                continue  #ignora e segue esperando, se era o ACK, o timeout resolve
            tp, s, _ = p  #tipo, seq e payload (o payload não interessa aqui)
            if tp == b"A" and s == seq:  #ACK do pacote certo, deu certo
                print(f"{log} ACK seq={seq} recebido")
                return  #só aqui a função termina com sucesso
            if tp == b"N":  #NAK: o receptor recebeu o pacote corrompido
                print(f"{log} NAK recebido -> retransmitindo")
                break  #retransmite na hora, sem esperar o timer acabar
            print(f"{log} ACK inesperado (seq={s}), ignorando")  #ACK com seq errado (de um pacote anterior), ignora e continua esperando
    raise ConnectionError(f"{log} Sem resposta após {MAX_RETRIES} tentativas (seq={seq})")  #esgotou as 30 tentativas, aborta a transferência


def rdt_recv(sock, expected, log, addr=None, timeout=None):
    """Recebe o próximo pacote com seq == expected, enviando ACK/NAK.
    Retorna (tipo, payload, endereço_do_remetente). Propaga socket.timeout."""
    sock.settimeout(timeout)  #tempo máximo de espera por pacote, None significa esperar pra sempre (usado pelo servidor aguardando cliente)
    while True:  #só sai com return quando chegar o pacote esperado
        raw, src = sock.recvfrom(PACKET_SIZE + 64)  #espera um pacote chegar (se estourar o timeout, lança socket.timeout pra quem chamou)
        if addr is not None and src != addr:  #se já sabemos quem é o remetente, ignora pacotes de outros
            continue
        p = parse_pkt(raw)  #confere o CRC e separa o pacote
        if p is None:  #chegou corrompido
            print(f"{log} Pacote CORROMPIDO -> enviando NAK")
            unreliable_send(sock, src, make_pkt(b"N", 1 - expected), log, "NAK")  #NAK com o seq do pacote anterior (1 - expected), pedindo pro remetente reenviar
            continue  #volta a esperar a retransmissão
        tipo, seq, payload = p  #pacote íntegro, separa as partes
        if seq == expected:  #é o pacote que a gente esperava
            print(f"{log} Recebido {tipo.decode()} seq={seq} OK ({len(payload)} bytes) -> ACK")
            unreliable_send(sock, src, make_pkt(b"A", seq), log, f"ACK seq={seq}")  #confirma pro remetente (o ACK também pode se perder)
            return tipo, payload, src  #entrega o pacote pra cima e quem chamou alterna o expected
        print(f"{log} DUPLICADO seq={seq} (esperava {expected}) -> reenviando ACK")  #seq errado = o remetente não recebeu nosso ACK anterior e retransmitiu
        unreliable_send(sock, src, make_pkt(b"A", seq), log, f"ACK seq={seq}")  #reenvia o ACK sem entregar o dado de novo (senão duplicaria o pedaço)


def linger(sock, addr, last_seq, log): #resolve o problema do último ACK perdido.
   
    fim = time.time() + LINGER #Guarda o instante em que a espera termina
    while fim - time.time() > 0: #Loop enquanto houver tempo
        sock.settimeout(fim - time.time()) #configura o recvfrom para esperar só o tempo que sobra, e não um valor fixo. Assim o prazo total é respeitado mesmo depois de vários pacotes recebidos
        try: #silêncio significa que o remetente recebeu o ACK e parou de retransmitir.
            raw, src = sock.recvfrom(PACKET_SIZE + 64)
        except socket.timeout:
            break
        p = parse_pkt(raw) #Reagir a um duplicado
        if src == addr and p and p[1] == last_seq:
            print(f"{log} Último pacote duplicado -> reenviando ACK")
            unreliable_send(sock, src, make_pkt(b"A", last_seq), log, f"ACK seq={last_seq}")
            fim = time.time() + LINGER   # sender ainda ativo: renova a espera


def send_bytes(sock, addr, filename, data, log_prefix="[ENVIO]"):  #Vamos fragmentar o data e enviar de forma confiavel
    total = max(1, math.ceil(len(data) / CHUNK_SIZE)) #numero de pacotes necessarios
    meta = json.dumps({"filename": filename, "filesize": len(data),"total_chunks": total}).encode("utf-8") #monta um dicionário Python com as infos que o outro lado precisa saber antes de receber os dados
    print(f"{log_prefix} Iniciando envio de '{filename}' ({len(data)} bytes, {total} pacotes de dados) -> {addr}")  # log do envio dos metadado
    
    seq = 0 #usando bit alternate, sendo o primeiro numero de sequencia o 0
    rdt_send(sock, addr, b"M", seq, meta, log_prefix)#envia os metadados do arquivo usando o protocolo RDT, com o número de sequência que está armazenado em seq
    seq ^= 1 #usando um xor para o proximo num de sequencia ser 1
    
    for i in range(total): #percorre o arquivo fragmentado, enviando um pacote de dados por vez usando o protocolo rdt e alternando o número de seq entre 0 e 1
        chunk = data[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]
        rdt_send(sock, addr, b"D", seq, chunk, log_prefix)
        seq ^= 1
    print(f"{log_prefix} Envio de '{filename}' concluído ({total} pacotes).")


def send_file(sock, addr, filepath, log_prefix="[ENVIO]"): #Lê um arquivo do disco e envia via send_bytes, usando o nome base do arquivo.
    filename = os.path.basename(filepath) #extrai o nome do arquivo
    with open(filepath, "rb") as f: #abre o arquivo em modo binário 
        data = f.read() #Leia todo o conteúdo do arquivo e  colque os bytes na variável data 
    send_bytes(sock, addr, filename, data, log_prefix)  #envia pra send_bytes, já com nome+conteúdo em mãos
    return filename, data


def recv_bytes(sock, log_prefix="[RECEBIMENTO]", addr=None, first_timeout=None, timeout=10):
    """Recebe metadados + todos os pacotes de dados. Retorna (nome, bytes, addr)."""
    expected = 0
    _, payload, addr = rdt_recv(sock, expected, log_prefix, addr, first_timeout)
    meta = json.loads(payload.decode("utf-8"))
    expected ^= 1
    total = meta["total_chunks"]
    print(f"{log_prefix} Metadados de {addr}: {meta['filename']} ({meta['filesize']} bytes, {total} pacotes)")
    partes = []
    while len(partes) < total:
        _, payload, _ = rdt_recv(sock, expected, log_prefix, addr, timeout)
        partes.append(payload)
        expected ^= 1
    linger(sock, addr, expected ^ 1, log_prefix)
    data = b"".join(partes)
    filename = os.path.basename(meta["filename"])
    print(f"{log_prefix} '{filename}' remontado com sucesso ({len(data)} bytes).")
    return filename, data, addr


def save_bytes(save_dir, filename, data):
    import os                                # importado aqui dentro só porque só é usado nesta função
    os.makedirs(save_dir, exist_ok=True)     # cria a pasta de destino se ela ainda não existir (não dá erro se já existir)
    path = os.path.join(save_dir, filename)  # monta o caminho completo do arquivo a ser salvo (pasta + nome)
    with open(path, "wb") as f:               # abre (ou cria) o arquivo em modo binário de escrita ("wb")
        f.write(data)                         # grava todos os bytes recebidos no arquivo
    return path                               # devolve o caminho completo, útil pra log/confirmação
