# BaixaVídeo Backend

Serviço experimental de extração para vídeos públicos do xHamster, usando yt-dlp e FFmpeg. Não contorna DRM, autenticação ou verificação de idade. Utilize somente conteúdo que você tem autorização para baixar.

Deploy: Render Web Service, runtime Docker, plano Free. Configure a variável DOWNLOAD_API_KEY com valor secreto forte. Endpoints: GET /health, GET /probe?url=... e GET /download?url=... . Probe e download exigem cabeçalho X-API-Key.

Limitações: acesso a páginas pode ser bloqueado pelo site; hospedagem gratuita possui limites de CPU, memória, banda e inatividade. Não publicar integração com Floot antes de validar um arquivo real.
