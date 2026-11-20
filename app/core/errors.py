"""Exceções do app e tradução de erros do yt-dlp/FFmpeg para mensagens compreensíveis."""
from __future__ import annotations


class NokkError(Exception):
    """Erro com mensagem já pronta para o usuário."""


class DownloadCancelled(Exception):
    pass


class FFmpegMissing(NokkError):
    pass


# (trecho em minúsculas na mensagem original, mensagem amigável). A ordem importa.
_RULES: list[tuple[tuple[str, ...], str]] = [
    (("private video",), "Este vídeo é privado. Só o dono pode acessá-lo."),
    (("members-only", "members only", "join this channel"),
     "Este vídeo é exclusivo para membros do canal e não pode ser baixado aqui."),
    (("confirm your age", "age-restricted", "age restricted", "inappropriate for some users"),
     "Este vídeo tem restrição de idade e exige login, o que o Nokk Downloader não faz."),
    (("drm",), "Este conteúdo é protegido por DRM e não pode ser baixado."),
    (("video unavailable", "has been removed", "no longer available", "this video is not available",
      "account associated with this video has been terminated", "copyright"),
     "Este vídeo está indisponível (removido, bloqueado na sua região ou excluído)."),
    (("premiere",), "Esta estreia ainda não começou. Tente novamente depois que o vídeo for publicado."),
    (("live event will begin", "is upcoming"), "Esta transmissão ao vivo ainda não começou."),
    (("sign in to confirm you", "confirm you’re not a bot", "confirm you're not a bot"),
     "O YouTube pediu verificação anti-robô para este acesso. Aguarde alguns minutos e tente de novo."),
    (("http error 429", "too many requests"),
     "O YouTube limitou temporariamente as requisições (erro 429). Aguarde alguns minutos."),
    (("unsupported url", "is not a valid url", "invalid url"), "Link inválido. Cole um link de vídeo ou Short do YouTube."),
    (("getaddrinfo failed", "name or service not known", "temporary failure in name resolution",
      "network is unreachable", "timed out", "connection reset", "connection refused",
      "unable to download", "urlopen error", "remote end closed", "transporterror", "unable to connect",
      "proxy"),
     "Falha de conexão. Verifique sua internet e tente novamente."),
    (("no space left", "disk full", "errno 28"), "Sem espaço em disco na pasta de destino."),
    (("permission denied", "access is denied", "errno 13"), "Sem permissão para gravar na pasta de destino."),
    (("requested format is not available", "requested format not available"),
     "A qualidade escolhida não está disponível para este vídeo. Escolha outra."),
    (("ffmpeg", "ffprobe", "postprocessing", "conversion failed", "invalid data found"),
     "O FFmpeg falhou ao processar o arquivo. Tente novamente; se persistir, atualize o FFmpeg."),
]


def friendly_message(exc: BaseException) -> str:
    if isinstance(exc, NokkError):
        return str(exc)
    raw = str(exc)
    low = raw.lower()
    for needles, message in _RULES:
        if any(n in low for n in needles):
            return message
    cleaned = raw.replace("ERROR:", "").strip()
    # remove códigos ANSI/prefixos como "[youtube] id:" para não poluir a UI
    cleaned = cleaned.split("\n")[0]
    if len(cleaned) > 220:
        cleaned = cleaned[:217] + "..."
    return f"Não foi possível concluir a operação: {cleaned}" if cleaned else "Erro desconhecido."
