# Dependências redistribuídas

O build exige `ffmpeg.exe`, `ffprobe.exe` e `node.exe` nesta pasta, além de `licenses/` com as licenças e informações de origem de cada distribuição.
Use binários Windows x64 de fontes oficiais/confiáveis. Não versione os executáveis.
FFmpeg e FFprobe devem vir da mesma distribuição. A licença exata depende da configuração dessa distribuição; preserve a licença, a origem e as informações de código-fonte correspondentes.
O aplicativo passa os caminhos absolutos ao yt-dlp, sem alterar o PATH do usuário.
