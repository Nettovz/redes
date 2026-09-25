# Projeto de Redes 2026.2 — Parte 1: Transmissão de Arquivos com UDP

**Disciplina:** CIN0018 - Fundamentos de Redes de Computadores
**Docente:** Renato Mariz de Moraes
**Integrantes:** _(preencher)_

## Descrição

Aplicação cliente-servidor em Python que transfere arquivos entre duas
máquinas (ou processos) usando sockets **UDP**. O cliente envia um arquivo
ao servidor, que o armazena com um novo nome (prefixo `servidor_`) e o
devolve ao cliente para confirmar o recebimento (que salva com prefixo
`cliente_`). A comunicação usa pacotes de até 1024 bytes, com fragmentação
e remontagem para arquivos maiores que esse limite. Não há mecanismos de
confiabilidade (ACK/NAK/retransmissão), conforme especificado para esta
etapa.

## Arquivos

| Arquivo | Função |
|---|---|
| `udp_protocol.py` | Módulo com o protocolo de fragmentação/remontagem, compartilhado por cliente e servidor. |
| `servidor.py` | Servidor UDP: recebe arquivos, armazena e devolve como confirmação. |
| `cliente.py` | Cliente UDP: envia um arquivo e salva a confirmação devolvida pelo servidor. |

### `udp_protocol.py`

Contém 4 funções usadas pelos outros dois scripts:

- **`send_bytes(sock, addr, filename, data, log_prefix)`** — fragmenta
  `data` em pacotes de até 1019 bytes úteis e envia pelo socket. Antes dos
  dados, envia um pacote de metadados (JSON com `filename`, `filesize` e
  `total_chunks`).
- **`send_file(sock, addr, filepath, log_prefix)`** — lê um arquivo do
  disco (em modo binário) e chama `send_bytes` internamente. Usado pelo
  cliente, que só tem o caminho do arquivo em mãos.
- **`receive_bytes(sock, log_prefix)`** — bloqueia até receber o pacote de
  metadados e todos os pacotes de dados correspondentes, remontando o
  arquivo original na ordem certa pelo número de sequência de cada pacote.
- **`save_bytes(save_dir, filename, data)`** — cria a pasta de destino (se
  não existir) e grava os bytes recebidos em disco.

### `servidor.py`

Fica em loop infinito, escutando na porta indicada (`5000` por padrão):

1. Recebe um arquivo completo via `receive_bytes`.
2. Salva em `servidor_storage/`, prefixando o nome com `servidor_`.
3. Reenvia o mesmo conteúdo de volta ao endereço do cliente que o mandou,
   como confirmação.
4. Volta a escutar (não trava se um cliente cair — só se Ctrl+C for
   pressionado).

### `cliente.py`

Fluxo linear, uma execução por arquivo:

1. Lê o caminho do arquivo, host e porta do servidor pelos argumentos da
   linha de comando.
2. Envia o arquivo via `send_file`.
3. Aguarda (com timeout de 10s) a devolução do servidor.
4. Salva a cópia recebida em `cliente_storage/`, prefixando com `cliente_`.
5. Compara o conteúdo devolvido com o original e avisa se são idênticos.

## Como executar

Abrir **dois terminais** na pasta do projeto (o servidor fica bloqueado
escutando, por isso precisa de um terminal só pra ele):

**Terminal 1 — servidor:**
```bash
python servidor.py 5000
```

**Terminal 2 — cliente:**
```bash
python cliente.py caminho\para\arquivo.txt 127.0.0.1 5000
```

Se host e porta forem omitidos, o cliente usa `127.0.0.1` e `5000` por
padrão.

## Protocolo (resumo técnico)

- Pacotes UDP de até 1024 bytes.
- **Pacote de metadados:** `b"M" + JSON{filename, filesize, total_chunks}`
  — enviado uma vez, antes dos dados.
- **Pacote de dados:** `b"D" + seq(4 bytes, big-endian) + até 1019 bytes`
  — um por fragmento do arquivo.
- O destinatário agrupa os pacotes de dados pelo número de sequência e os
  concatena na ordem correta para remontar o arquivo.
- Sem ACK/NAK/retransmissão nesta etapa — arquivos muito grandes podem
  falhar por perda de pacote sem recuperação (comportamento esperado e
  aceitável pelo enunciado).

## Testes realizados

- ✅ Arquivo `.txt` pequeno (1 pacote) — transferido e devolvido com
  sucesso, conteúdo idêntico.
- ✅ Arquivo binário >1024 bytes (múltiplos pacotes) — fragmentado,
  remontado corretamente nos dois lados.
- ✅ Verificação de integridade no cliente (comparação byte a byte entre
  enviado e devolvido) confirmou sucesso em ambos os casos.

## Observações

- Como o protocolo trabalha com bytes puros, qualquer tipo de arquivo
  (txt, jpeg, pdf etc.) é suportado sem alterações no código.
- Recomenda-se testar com arquivos de até algumas centenas de KB — sem
  confiabilidade, arquivos muito grandes (vários MB) têm risco de travar
  esperando um pacote perdido que nunca chega (o timeout de 10s no
  cliente evita que ele fique preso indefinidamente).

  **Integrantes:**
- Deoclecio Ivo de Melo Netto
- Eduardo Gabriel de Souza Pedroza
- Jefferson Pereira de Oliveira Junior
- Pedro Gabriel Alves da Silva

