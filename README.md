# Projeto de Redes 2026.2 — Parte 2: RDT 3.0 sobre UDP

**Disciplina:** CIN0018 - Fundamentos de Redes de Computadores
**Docente:** Renato Mariz de Moraes
**Grupo:** 05

**Integrantes:**
- Deoclécio Ivo de Melo Netto
- Eduardo Gabriel de Souza Pedroza
- Jefferson Pereira de Oliveira Junior
- Pedro Gabriel Alves da Silva

## Descrição

Evolução da parte 1: o cliente envia um arquivo ao servidor, que o armazena
(prefixo `servidor_`) e o devolve ao cliente (salvo com prefixo `cliente_`).
Agora a transferência usa **RDT 3.0 (stop-and-wait) implementado na camada de
aplicação**, sobre socket **UDP**, com um **gerador aleatório de perdas** no
canal e **logs detalhados** em tempo de execução.

## Arquivos

| Arquivo | Função |
|---|---|
| `rdt.py` | Protocolo RDT 3.0: pacotes, checksum, ACK/NAK, timer, retransmissão, canal com perdas, envio/recebimento de arquivos. |
| `servidor.py` | Servidor: recebe, armazena em `servidor_storage/` e devolve o arquivo. |
| `cliente.py` | Cliente: envia o arquivo, recebe a devolução, salva em `cliente_storage/` e confere a integridade. |

## Como executar

Requer Python 3 (somente biblioteca padrão). Use **dois terminais** na pasta do projeto.

Os parâmetros são **posicionais** (não existem flags como `--loss`): a ordem importa e,
para informar um parâmetro, é preciso informar todos os que vêm antes dele.

**Terminal 1 — servidor:**
```bash
python servidor.py [porta] [loss] [corrupt] [timeout]
```
```bash
python servidor.py 5000 0.3 0.1 0.3
```

**Terminal 2 — cliente:**
```bash
python cliente.py arquivo [host] [porta] [loss] [corrupt] [timeout]
```
```bash
python cliente.py caminho/do/arquivo.pdf 127.0.0.1 5000 0.3 0.1 0.3
```

### Parâmetros

| Posição (servidor) | Posição (cliente) | Parâmetro | Obrigatório | Padrão | Descrição |
|---|---|---|---|---|---|
| — | 1 | `arquivo` | **sim** | — | Caminho do arquivo a ser enviado. |
| — | 2 | `host` | não | `127.0.0.1` | IP do servidor. |
| 1 | 3 | `porta` | não | `5000` | Porta UDP do servidor. |
| 2 | 4 | `loss` | não | `0.2` | Probabilidade (0 a 1) de **perder** cada pacote enviado (dados, ACK e NAK). |
| 3 | 5 | `corrupt` | não | `0.1` | Probabilidade (0 a 1) de **corromper** cada pacote enviado (provoca NAK). |
| 4 | 6 | `timeout` | não | `0.3` | Tempo, em segundos, que o remetente espera o ACK antes de retransmitir. |

Exemplos:

```bash
# Tudo padrão (servidor na porta 5000, perda 20%, corrupção 10%, timeout 0.3 s)
python servidor.py
python cliente.py foto.jpg

# Canal sem falhas
python servidor.py 5000 0 0
python cliente.py foto.jpg 127.0.0.1 5000 0 0

# Perda alta, timeout menor para acelerar testes locais
python servidor.py 5000 0.4 0.1 0.05
python cliente.py arquivo.pdf 127.0.0.1 5000 0.4 0.1 0.05

# Servidor em outra máquina da rede
python cliente.py arquivo.zip 192.168.0.10 5000
```

Cliente e servidor aplicam a perda cada um no que enviam, então os valores de `loss`,
`corrupt` e `timeout` podem (e costumam) ser informados nos dois lados. Dica: com perda
alta, use arquivos de até algumas centenas de KB e `timeout` menor (ex.: `0.05`) em
testes locais.

Se o `arquivo` não existir, o cliente encerra com a mensagem `[CLIENTE][ERRO] Arquivo não encontrado`.
Se `python cliente.py` for chamado sem argumentos, é exibido o uso:
`Uso: python cliente.py arquivo [host] [porta] [loss] [corrupt] [timeout]`.

## Protocolo

Pacote UDP (≤ 1024 bytes): `tipo (1 B) | seq (1 B) | payload | CRC32 (4 B)`, com até 1018 bytes de dados.

- **Tipos:** `M` metadados (JSON com nome, tamanho e nº de pacotes), `D` dados, `A` ACK, `N` NAK.
- **Numeração sequencial 0/1**, alternando a cada pacote (cada transferência começa em 0).
- **Remetente (`rdt_send`):** envia o pacote, inicia o timer e espera o ACK de mesmo `seq`.
  Em **timeout** ou ao receber **NAK**, retransmite; ACKs com `seq` errado ou corrompidos são ignorados.
  Desiste após 30 tentativas.
- **Receptor (`rdt_recv`):** pacote **corrompido** (CRC inválido) → envia **NAK**;
  `seq` esperado → entrega e envia **ACK**; **duplicado** → descarta e reenvia o ACK.
- **Canal (`unreliable_send`):** sorteia perda/corrupção antes de cada envio e registra `[PERDA SIMULADA]` / `[CORRUPÇÃO SIMULADA]`.
- **Encerramento (`linger`):** depois do último pacote, o receptor continua reenviando o ACK
  enquanto o remetente retransmitir, pois o último ACK pode ter sido perdido.
- Arquivos são tratados como bytes puros: qualquer extensão é suportada.

## Logs

Prefixos `[CLIENTE][ENVIA]`, `[CLIENTE][RECEBE]`, `[SERVIDOR][RECEBE]`, `[SERVIDOR][ENVIA]`.
Mensagens principais: `Enviando`, `ACK recebido`, `TIMEOUT`, `RETRANSMITINDO`,
`NAK recebido`, `Pacote CORROMPIDO -> enviando NAK`, `DUPLICADO ... reenviando ACK`,
`[PERDA SIMULADA]`, `[CORRUPÇÃO SIMULADA]`.

## Testes realizados

- `.txt`, `.jpg`, `.pdf`, `.zip` e binário de 150 KB (≈148 pacotes) transferidos com perda e corrupção, conteúdo idêntico (verificado por comparação byte a byte).
- Arquivo vazio e arquivo menor que 1 pacote.
- Execuções repetidas com 30% e 40% de perda: todas concluídas com sucesso.
- Canal sem perdas: apenas ACKs, sem retransmissão.

## Observações

- Corrigido um bug da parte 1: o número de pacotes era calculado com 1024 em vez do tamanho útil do pacote, truncando arquivos grandes.
- O servidor atende um cliente por vez. Se uma transferência falhar após as tentativas, ela é abortada e o servidor volta a escutar.
- Como em qualquer protocolo stop-and-wait, perdas altas deixam a transferência lenta (cada perda custa um timeout).
