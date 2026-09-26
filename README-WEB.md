# Central de mídia — protótipo Flask

A aplicação web foi adicionada ao ambiente de linha de comando existente. O README.md e requirements.txt originais permanecem como referência para o CLI. Use requirements-web.txt para a aplicação: ele declara apenas dependências diretas, evitando levar o congelamento completo do ambiente Windows ao container Linux.

## Executar no Windows

Na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv\Scripts\python.exe -m flask --app app:create_app run --host 127.0.0.1 --port 5000
```

Abra http://127.0.0.1:5000. O servidor Flask serve para teste local. Gunicorn roda no container Linux.

FFmpeg e um runtime JavaScript (Deno ou Node.js 20+) devem estar no PATH para a execução local. Deno tem prioridade; Node.js também é habilitado explicitamente nos dois provedores. Este computador já tem FFmpeg e Node.js 24. Alternativamente, defina FFMPEG_PATH com o caminho completo do ffmpeg.exe. O FFmpeg baixado exclusivamente para a pasta interna do spotDL não é descoberto automaticamente por esta aplicação. Para Deno, consulte https://docs.deno.com/runtime/getting_started/installation/ .

## Docker

```powershell
docker build -t central-midia .
docker run --rm --init -p 127.0.0.1:5000:5000 central-midia
```

A imagem instala FFmpeg, inclui Deno e roda como usuário sem privilégios. Os áudios da pasta e o ambiente .venv não entram na imagem.

## O que está incluído

- Interface responsiva em português, sem dependências externas de frontend.
- Detecção de Spotify/YouTube usando o mesmo validador do backend.
- Spotify: faixa individual em MP3 via spotDL; metadados do Spotify e áudio de outros provedores, com possibilidade de correspondência incorreta.
- YouTube: MP3 ou MP4 até 720p via yt-dlp; apenas um vídeo, até 20 minutos, sem transmissões ao vivo. O formato MP4 solicitado pode não estar disponível em todo vídeo.
- Confirmação obrigatória de direito/autorização na interface e no backend; essa declaração não verifica licenças automaticamente.
- URLs HTTPS de hosts e caminhos conhecidos, sem credenciais ou portas arbitrárias. Parâmetros de playlist são descartados.
- Processos sem shell, diretório temporário por requisição e remoção após a resposta fechar ou ocorrer erro.
- Limite final de 200 MB; não equivale a uma cota rígida de disco durante download/conversão. Streams temporários podem ocupar mais espaço.

## Gunicorn e limites

Não havia configuração Gunicorn anterior nesta pasta. gunicorn.conf.py define 2 processos, cada um com 2 threads (gthread), timeout e graceful_timeout de 240 segundos. MEDIA_TIMEOUT define o limite do subprocesso de download/conversão (180 segundos por padrão), encerrando também os processos filhos ao excedê-lo.

A execução é síncrona: cada preparo ocupa uma thread e mantém a conexão HTTP aberta. Quatro preparos simultâneos podem ocupar toda a capacidade configurada. Não há fila, progresso percentual, histórico ou cancelamento pelo navegador. Fechar a página não cancela imediatamente o processo; ele termina normalmente ou pelo limite de tempo. O navegador recebe o arquivo completo antes de iniciar o salvamento e pode usar até cerca de 200 MB de memória por arquivo.

Em gthread, o timeout do Gunicorn detecta silêncio do worker; NÃO é um limite de duração por requisição. O limite efetivo do download é MEDIA_TIMEOUT. Caso aumente esse valor, revise também graceful_timeout e os timeouts de qualquer proxy (por exemplo, proxy_read_timeout do nginx), deixando margem para a transferência do arquivo. A transferência ao navegador não está incluída no limite do subprocesso.

Reinícios forçados ou falhas do sistema podem deixar temporários; o descarte do container remove esses arquivos quando não há volume persistente em /tmp. Para mais usuários ou downloads longos, evolua para fila externa e armazenamento compartilhado, sem usar um dicionário em memória entre processos Gunicorn.

Este protótipo não tem autenticação nem controle por usuário. O comando acima publica apenas em localhost. Ao incorporar ao portal, registre media.bp na factory existente, adapte o template ao layout do portal e aplique a autenticação e os limites do portal antes de expor o endpoint à rede.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_media
```

Os testes cobrem validação, autorização, resposta de arquivo, limpeza, erro e timeout. Downloads externos são simulados; disponibilidade, bloqueios e correspondências dos provedores dependem de uma validação posterior com conteúdo autorizado. Não são usados os arquivos de áudio existentes como material de teste.

## Referências

- spotDL: https://spotdl.github.io/spotify-downloader/usage/
- yt-dlp / JavaScript: https://github.com/yt-dlp/yt-dlp/wiki/EJS
- Gunicorn gthread: https://docs.gunicorn.org/en/stable/design.html

