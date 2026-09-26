# spotify-downloader

Ambiente Python com [spotdl](https://github.com/spotDL/spotify-downloader) para baixar músicas, álbuns e playlists do Spotify (áudio obtido via YouTube/YouTube Music/SoundCloud, com metadados e capa embutidos).

## Setup

```powershell
# criar e ativar o ambiente virtual (já existe em .venv/)
.\.venv\Scripts\Activate.ps1

# instalar/atualizar dependências
.\.venv\Scripts\pip.exe install -r requirements.txt

# baixar o ffmpeg (necessário para converter/mixar áudio)
.\.venv\Scripts\spotdl.exe --download-ffmpeg
```

## Comandos principais

```powershell
# baixar uma música
spotdl download "https://open.spotify.com/track/..."

# baixar um álbum
spotdl download "https://open.spotify.com/album/..."

# baixar uma playlist
spotdl download "https://open.spotify.com/playlist/..."

# baixar todas as músicas de um artista
spotdl download "https://open.spotify.com/artist/..."

# baixar por busca (sem link)
spotdl download "nome da musica artista"

# baixar suas músicas curtidas (requer --user-auth)
spotdl download saved --user-auth

# baixar todas as suas playlists
spotdl download all-user-playlists --user-auth
```

## Outras operações

```powershell
# salvar metadados em arquivo, sem baixar áudio ainda
spotdl save "URL" --save-file playlist.spotdl

# baixar depois a partir do arquivo salvo
spotdl download playlist.spotdl

# sincronizar uma pasta com uma playlist (adiciona novas, remove removidas)
spotdl sync "URL" --save-file playlist.spotdl

# atualizar metadados de arquivos de áudio já baixados
spotdl meta "arquivo.mp3"

# obter apenas a URL de download (sem baixar)
spotdl url "URL do Spotify"

# abrir interface web
spotdl web
```

## Opções úteis

```powershell
# escolher formato de saída
spotdl download "URL" --format mp3

# escolher bitrate
spotdl download "URL" --bitrate 320k

# definir pasta/padrão de nome de saída
spotdl download "URL" --output "Musicas/{artist}/{album}/{title}.{output-ext}"

# trocar o provedor de áudio (fallback em ordem)
spotdl download "URL" --audio youtube-music youtube

# gerar letras sincronizadas (.lrc)
spotdl download "URL" --generate-lrc

# ver todas as opções disponíveis
spotdl --help
```

## Autenticação (opcional)

Para baixar `saved`, `all-user-playlists` e afins é preciso autenticar com sua conta Spotify:

```powershell
spotdl download saved --user-auth --client-id SEU_CLIENT_ID --client-secret SEU_CLIENT_SECRET
```

As credenciais podem ser criadas em https://developer.spotify.com/dashboard.
