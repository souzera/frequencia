# Frequência — MP3 no desktop

Aplicativo Python + **pywebview** para Windows, com tema claro, **Cascadia Code incluída**, seleção de músicas e processamento por **yt-dlp + FFmpeg**.

## Executar

Requer Python 3.12, Microsoft Edge WebView2 Runtime e os componentes de áudio abaixo.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe desktop_app.py
```

Em desenvolvimento, coloque `ffmpeg.exe`, `ffprobe.exe` e `node.exe` em `vendor/`. Como alternativa, o aplicativo também encontra esses programas no PATH existente. Não é necessário criar variáveis de ambiente se os binários estiverem em `vendor/`.

## Uso

1. Cole um link e clique em **Conferir link**.
2. Para playlists, todas as músicas acessíveis já vêm selecionadas. Desmarque o que não quiser.
3. Clique em **Baixar seleção**. A interface mostra fila, download, conversão e conclusão por música.
4. Use **Abrir pasta** para acessar os arquivos.

A pasta padrão é a pasta Downloads reconhecida pelo Windows, inclusive quando redirecionada. Em **Configurações**, escolha outra pasta e a taxa MP3 (128, 192 ou 320 kbps). As preferências são salvas atomicamente em `%LOCALAPPDATA%\Frequencia\settings.json`. Alterações valem para o próximo lote; um lote em andamento mantém sua configuração inicial.

É possível cancelar a consulta ou o lote. O processo de download e seus subprocessos, incluindo FFmpeg, são encerrados; arquivos concluídos são mantidos. Arquivos `.part` podem permanecer para retomada. Uma falha não interrompe as outras faixas. Ao terminar, as faixas que falharam continuam disponíveis para uma nova tentativa. A seleção atual é mantida apenas durante a sessão, sem histórico persistente.

## Como o tipo de link é identificado?

A classificação é local, com `urllib.parse`, domínio exato, caminho e parâmetros. Não depende de scraping ou de chamadas de rede.

| Serviço | Individual | Playlist |
|---|---|---|
| Spotify | `open.spotify.com/track/ID` | `open.spotify.com/playlist/ID` |
| YouTube | `youtube.com/watch?v=ID`, `youtu.be/ID`, `/shorts/ID`, `/live/ID`, `/embed/ID` | `youtube.com/playlist?list=ID` |

São aceitos os domínios `www.youtube.com`, `m.youtube.com` e `music.youtube.com`, além dos caminhos localizados do Spotify, como `/intl-pt/track/ID`.

**Vídeo com `v` e `list`:** o padrão é somente o vídeo. Uma opção explícita permite carregar a playlist inteira. Parâmetros de compartilhamento e rastreamento são removidos na normalização. Links HTTP, domínios parecidos, credenciais embutidas, portas alternativas, álbuns e encurtadores `spotify.link` não são aceitos. Para o Spotify, copie o endereço completo do conteúdo.

## Como funciona o Spotify?

O Spotify fornece **metadados**, não o arquivo de áudio. O adaptador de metadados utiliza spotDL; o áudio é pesquisado e baixado no YouTube com yt-dlp. A busca compara nome, artista e duração entre até cinco candidatos e mostra o título encontrado. Os nomes e artistas do Spotify são gravados nas tags ID3 do MP3.

O suporte se destina a faixas e playlists públicas acessíveis pelo adaptador. Playlists privadas, conteúdo removido, limites de requisição e mudanças nos provedores podem impedir a consulta. Esta versão não oferece login Spotify. A correspondência é heurística: versões diferentes ainda podem ser encontradas; use o link direto do YouTube quando precisar de uma gravação específica. Converter para 320 kbps não recupera qualidade ausente na fonte.

## Build e instalador

Como gerar o pacote Windows, o instalador e usar o build automatizado via GitHub Actions: veja o [BUILD.md](BUILD.md).

## Arquitetura

- `desktop_app.py`: inicialização pywebview e entrada do worker.
- `desktop/links.py`: validação e classificação de URLs.
- `desktop/settings.py`: preferências, pasta Downloads e resolução dos binários.
- `desktop/api.py`: ponte restrita para a UI, estado protegido por lock, subprocesso e cancelamento.
- `desktop/worker.py`: metadados, busca de correspondências, download, conversão e tags.
- `desktop/ui/`: interface local, sem CDN, com fonte embarcada.
- `packaging/`: receita PyInstaller e instalador Inno Setup.

Chamadas de rede e conversão não executam na thread da janela. A UI consulta snapshots do estado, não recebe comandos JavaScript construídos com títulos de músicas. Conteúdo dos provedores é renderizado com `textContent`. O aplicativo não expõe uma API Flask de download; o servidor local interno do pywebview serve os arquivos da interface. A política de conteúdo permite a geração de funções necessária à ponte do pywebview, sem carregar scripts externos.

## Verificação

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests/smoke_window.py
```

A suíte desktop cobre as quatro categorias e variantes, URLs ambíguas/inválidas, configurações corrompidas, pasta padrão, preferência por binários embarcados, estado da fila, cancelamento, falhas parciais, metadados Spotify e correspondências. Inclui uma conversão **real e offline**: gera um tom original, converte para MP3 com yt-dlp/FFmpeg e verifica o codec com FFprobe. Testes dos provedores usam respostas simuladas; não representam uma validação de disponibilidade de toda playlist na Internet.

O teste opcional `smoke_window.py` abre uma janela WebView2 temporária e verifica inicialização da ponte Python, carregamento da fonte, ausência de rolagem horizontal e navegação para Configurações.

`tests/smoke_frozen.py` verifica o worker empacotado, a fonte e os executáveis embarcados sem rede. `tests/smoke_providers.py` é uma consulta opcional à Internet, apenas de metadados públicos; não baixa áudio. Os relatórios ficam em `build/`. Na verificação desta entrega, os quatro tipos foram consultados com sucesso: vídeo YouTube (Big Buck Bunny), playlist YouTube, faixa Spotify (Blinding Lights) e playlist Spotify com 50 faixas. A conversão para MP3 foi validada com áudio original gerado localmente. Passaram 18 testes desktop e o teste da janela real com WebView2. A geração de instalador requer Inno Setup; o compilador não estava disponível nesta máquina.

## Referências

- [pywebview: API e ponte JavaScript](https://pywebview.flowrl.com/api/)
- [pywebview: empacotamento](https://pywebview.flowrl.com/guide/freezing)
- [yt-dlp: dependências e opções](https://github.com/yt-dlp/yt-dlp)
- [spotDL: uso e fontes de áudio](https://spotdl.readthedocs.io/en/latest/usage/)
- [Microsoft: WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)
