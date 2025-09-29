# sistema_gestao_augusto_abou
Instale o ambiente no Windows:

Instale Python para Windows (baixe do site oficial python.org).

Abra o terminal (PowerShell ou CMD).

Navegue até a pasta do seu projeto.

Crie e ative o ambiente virtual: python -m venv venv e depois .\venv\Scripts\activate.

No linux: python -m venv venv e depois source venv/bin/activate.

Instale as dependências: pip install -r requirements.txt.

Execute o PyInstaller: Rode o seguinte comando para gerar o executavel:

pyinstaller --onefile --noconsole --add-data templates:templates --add-data static:static app.py

Execute o Script: Com o venv ativo, simplesmente rode:

python app.py