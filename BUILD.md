# Build — Frequência

Como gerar o pacote Windows, o instalador e usar o build automatizado via GitHub Actions. Para rodar a partir do código-fonte, veja o [README](README.md).

## FFmpeg, FFprobe e Node no instalador

**O empacotamento inclui FFmpeg, FFprobe e Node. Não exige Python nem alterações no PATH na máquina de destino.** Os executáveis são localizados em `_internal/vendor/` e seus caminhos absolutos são passados ao yt-dlp. FFprobe acompanha FFmpeg; Node atende ao runtime JavaScript utilizado pelo extrator do YouTube. Os scripts EJS vêm na dependência `yt-dlp[default]`.

O aplicativo usa WebView2 para renderizar a janela. O instalador verifica a presença do runtime e informa quando ele precisa ser instalado. O runtime WebView2 não é redistribuído neste pacote.

### É portable?

A pasta executável pode ser copiada e usada sem instalação, desde que o Windows de destino tenha WebView2. Copie a pasta inteira. Não é um modo totalmente portátil: as preferências ficam em `%LOCALAPPDATA%\Frequencia` e o destino padrão dos MP3 é a pasta Downloads do usuário. Essas preferências e músicas não acompanham automaticamente a cópia para outro computador.

O ícone (equalizador em barras) é compartilhado pela interface, janela, executáveis e receita do instalador. Os arquivos SVG, PNG e ICO estão em `desktop/ui/assets/`; `packaging/create_icon.py` os gera. A atualização somente de arte de uma distribuição existente pode ser feita com `packaging/update_icon.py`, que cria uma cópia separada e preserva o código empacotado. Alterações funcionais continuam exigindo o build completo.

## Gerar o pacote Windows

1. Instale as dependências desktop e `pyinstaller`.
2. Coloque os três executáveis Windows x64 em `vendor/`, com FFmpeg e FFprobe da mesma distribuição.
3. Inclua as licenças e informações de origem das distribuições em `vendor/licenses/`. A fonte leva sua licença em `desktop/ui/fonts/OFL.txt`.
4. Execute:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller packaging/frequencia.spec --noconfirm
```

O resultado fica em `dist/Frequencia/Frequencia.exe`. **Distribua a pasta `dist/Frequencia` inteira**, incluindo `FrequenciaWorker.exe` e `_internal`, não apenas o executável principal. A janela não abre um console; o worker é um executável separado para ter comunicação por pipes e cancelamento confiável no Windows.

## Gerar o instalador

Instale **Inno Setup 6** e compile `packaging/installer.iss`, ou execute:

```powershell
powershell -File packaging/build.ps1
```

O script gera primeiro o pacote e, quando encontra o compilador Inno Setup, gera `dist/installer/Frequencia-Setup-1.0.0.exe`. Sem o compilador, entrega a pasta executável e informa a pendência. A instalação é por usuário, sem administrador; a desinstalação não apaga músicas ou preferências. O pacote ainda não possui assinatura digital.

A versão do instalador (`AppVersion` e o nome do arquivo) vem de `MyAppVersion`, definido em `packaging/installer.iss` com padrão `1.0.0`. Para gerar outra versão sem editar o arquivo:

```powershell
ISCC.exe /DMyAppVersion=1.2.3 packaging/installer.iss
```

## Build automatizado (GitHub Actions)

`.github/workflows/release.yml` builda o instalador em um runner `windows-latest` e publica o resultado como GitHub Release. Ele resolve `vendor/ffmpeg.exe`, `vendor/ffprobe.exe` e `vendor/node.exe` sozinho, baixando-os de fontes oficiais (não são versionados no repositório), então roda o PyInstaller e o Inno Setup como nos passos manuais acima.

Duas formas de disparar:

- **Tag de versão:** `git tag v1.2.3 && git push origin v1.2.3` builda e cria a Release automaticamente, anexando `Frequencia-Setup-1.2.3.exe`.
- **Manual:** aba **Actions → Release Windows installer → Run workflow** no GitHub, informando a versão; útil para testar o build sem publicar uma Release (o instalador fica disponível como artifact do run).
