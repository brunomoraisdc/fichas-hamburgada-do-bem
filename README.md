# Fichas Hamburgada do Bem

Sistema que substitui o preenchimento manual das "Fichas de Autorização" do
evento Hamburgada do Bem por captura fotográfica + IA, com validação humana
antes de salvar os dados.

## Como funciona

1. O voluntário tira uma foto da ficha preenchida pelo responsável, direto
   do navegador do celular (acesso via QR code, sem instalar app nenhum).
2. A IA (Gemini 2.5 Flash) extrai os dados da ficha — criança, responsável,
   autorizações.
3. O voluntário revisa os dados extraídos numa tela de validação; campos que
   a IA não teve certeza na leitura ficam destacados pra revisão manual.
4. Ao confirmar, o dado validado é salvo no banco local (SQLite, fonte da
   verdade) e sincronizado com uma planilha do Google, pra quem acompanha o
   evento remotamente.

## Stack

- **Backend:** FastAPI + SQLite + Gemini 2.5 Flash (extração) + Google
  Sheets API (relatório)
- **Frontend:** HTML/CSS/JS puro, sem framework, mobile-first
- **Custo:** zero — tudo roda em free tier ou localmente, sem hosting pago

## Decisões técnicas

Algumas decisões de arquitetura que valem explicar:

- **Captura de foto sem `getUserMedia`.** A Fase 1 roda em HTTP puro sobre
  IP local (notebook + hotspot no próprio evento, sem certificado). Como
  `getUserMedia` exige contexto seguro (HTTPS ou `localhost`), optei por
  `<input type="file" capture="environment">`, que funciona normalmente em
  HTTP puro. O trade-off: perco a garantia de código de que a imagem nunca
  vira arquivo em disco — com `getUserMedia` o frame vai direto pro
  `<canvas>` em memória; com `capture`, isso depende do comportamento do
  navegador/SO (que na prática não persiste a foto na galeria, mas não é
  uma garantia formal). HTTPS com certificado autoassinado resolveria isso,
  mas o aviso de "conexão não segura" do navegador seria atrito demais pra
  dezenas de voluntários não-técnicos num evento de um dia — priorizei
  adoção sobre a garantia técnica extra.

- **SQLite como fonte da verdade, Google Sheets só como espelho.** O
  relatório sincroniza automaticamente com uma planilha do Google após cada
  ficha validada, mas o banco local nunca depende dela: a sincronização é
  best-effort (se falhar, só loga um aviso) e cada chamada reescreve a
  planilha inteira a partir do SQLite — então uma falha isolada se
  autocorrige sozinha na próxima ficha validada, sem precisar de fila de
  retry.

- **Senha simples pra proteger endpoints administrativos.** Como o backend
  precisa ficar acessível pra rede inteira do hotspot (pros celulares dos
  voluntários chegarem no upload), qualquer aparelho conectado na mesma
  rede também conseguiria baixar o relatório com dados pessoais via
  `/api/export`, sem proteção nenhuma. Adicionei uma senha compartilhada
  simples nesse endpoint — suficiente pro risco real de um evento curto com
  poucas pessoas na rede, mas não seria a escolha certa se o sistema
  precisasse rodar por mais tempo ou pra um público maior.

## Como rodar

```
venv/Scripts/activate        # Windows
uvicorn backend.app:app --reload --port 8000
```

Requer uma chave de API do Gemini (`GEMINI_API_KEY`) num arquivo `.env` na
raiz do projeto. Com o servidor no ar, `http://127.0.0.1:8000/docs` expõe a
documentação interativa da API (gerada automaticamente pelo FastAPI).
