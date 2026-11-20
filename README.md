# Nokk Downloader

Aplicativo desktop (Windows, também roda em Linux/macOS) para baixar vídeos do YouTube **100% localmente**:
escolha formato (MP4/MP3), qualidade e o **trecho exato** do vídeo. Sem backend, sem serviços pagos, sem enviar nada a servidores.

> Baixe apenas conteúdo que você tem autorização para baixar. O app não contorna DRM, login, restrição de idade
> nem qualquer proteção de acesso, e não lê cookies do navegador.

## Instalação

Requisitos: Python 3.10+ e FFmpeg.

```powershell
pip install -r requirements.txt
winget install Gyan.FFmpeg        # FFmpeg (o app avisa e orienta se não encontrar)
python main.py
```

O app procura o FFmpeg na pasta `ffmpeg/` ao lado do app, no PATH e em locais comuns do Windows (winget, `C:\ffmpeg\bin`).

**Runtime JavaScript (recomendado):** o YouTube atual exige que o yt-dlp execute JavaScript para resolver os links.
Instale o Deno (`winget install DenoLand.Deno`) ou o Node.js; o app detecta sozinho. Sem isso, algumas qualidades podem faltar.
Mantenha o yt-dlp atualizado (`pip install -U yt-dlp`), pois o YouTube muda com frequência.

## Atalho no Windows (sem digitar comandos)

- `iniciar.bat` (duplo clique): instala as dependências na primeira vez e abre o app.
- `gerar_exe.bat` (duplo clique): gera `dist\NokkDownloader\NokkDownloader.exe` (e copia o FFmpeg junto, se estiver instalado). Distribua a pasta `dist\NokkDownloader` inteira.

## Como usar

1. Cole o link (vídeo normal ou Short) e clique em **Analisar**: aparecem miniatura, título, canal, duração e as qualidades realmente disponíveis.
2. Escolha **MP4** (qualidade: melhor, 2160p, 1440p, 1080p, 720p, 480p, 360p) ou **MP3** (320/256/192/128 kbps).
3. Opcional: preencha **Início** e **Fim** (`HH:MM:SS`, `MM:SS` ou segundos) para baixar só o trecho. Vazio = vídeo completo.
   Ex.: vídeo de 40 min, de `05:30` a `12:45` baixa apenas ~7 min.
4. Escolha a pasta (a última usada é lembrada) e clique em **Baixar**. Os downloads entram numa fila sequencial com progresso, velocidade, tamanho estimado e botão de cancelar.

## Decisões técnicas

| Tema | Decisão |
|---|---|
| Vídeo + áudio | Seletor de formato próprio (`core/youtube.py`): melhor trilha de vídeo ≤ qualidade + melhor áudio, baixadas **separadamente** e combinadas em MP4 pelo FFmpeg. Prefere H.264/AAC (compatível com tudo); em 1440p/2160p o YouTube só oferece VP9/AV1. |
| Vertical (Shorts) | A qualidade é medida pelo lado menor (1080×1920 = 1080p). |
| Recorte | `download_ranges` do yt-dlp: o FFmpeg pede **só a janela** ao servidor, sem baixar o vídeo inteiro. Em MP4 o trecho é recodificado em H.264 CRF 17 (corte exato no frame, sem perda visível). Se o recorte direto falhar, há plano B: baixa tudo e recorta localmente (`core/converter.py`). |
| MP3 | Melhor áudio original → `libmp3lame` CBR no bitrate escolhido, via FFmpeg próprio (não depende do ffprobe). |
| Arquivos parciais | Cada download usa uma pasta temporária oculta; cancelar/falhar não deixa lixo, e nunca sobrescreve arquivos existentes (`nome (1).mp4`). |
| Threads | `QThread` para análise e downloads; a UI nunca bloqueia. A fila (`workers/manager.py`) aceita N downloads simultâneos (`max_concurrent`); hoje é 1. |
| Configurações | JSON em `%APPDATA%\NokkDownloader\settings.json` (só preferências). SQLite fica para quando houver histórico. |

## Estrutura

```
main.py
app/
  core/      youtube.py (info, qualidades, seletor) · downloader.py · converter.py · ffmpeg.py · errors.py · models.py
  workers/   info_worker.py · download_worker.py · manager.py (fila)
  ui/        main_window.py · styles.py · icons.py · terms_dialog.py · components/
  utils/     validators.py (URL e minutagem) · settings.py · system.py
tests/       unitários + integração (yt-dlp e FFmpeg reais com servidor local) + UI offscreen
```

## Testes

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

Os testes de integração usam o yt-dlp e o FFmpeg reais contra um extrator local (sem internet): merge de vídeo+áudio,
limite de qualidade, recorte, MP3 com bitrate, cancelamento sem sobras, fila sequencial e a janela completa de ponta a ponta.

## Gerar o executável (opcional)

```powershell
pip install pyinstaller
pyinstaller --noconsole --name NokkDownloader --collect-all yt_dlp main.py
```
Coloque `ffmpeg.exe`/`ffprobe.exe` em `dist\NokkDownloader\ffmpeg\` para distribuir sem exigir instalação.

## Limitações conhecidas

- Lives em andamento, vídeos privados, de membros, com restrição de idade ou DRM não são baixados (mensagem explicativa).
- Cancelar durante a etapa final de combinação (FFmpeg) só tem efeito quando ela termina (segundos).
- O progresso de recortes é estimado pelo tempo processado pelo FFmpeg.
