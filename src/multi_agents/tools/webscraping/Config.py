# Fichier de base de données SQLite
CONFIG_DB_FILE = 'Airbnb.db'

# Fichier de sortie au format XLSX
CONFIG_OUTPUT_FILE = 'Data_out.xlsx'

# Nombre maximal de tentatives en cas d'erreur avant de quitter le programme
CONFIG_MAX_RETRIES = 15

# Délai entre les pages (s)
CONFIG_PAGE_DELAY_MIN = 1  # le temps d'attente avant de passer à la page suivante (secondes)
CONFIG_PAGE_DELAY_MAX = 2  # le temps d'attente avant de passer à la page suivante (secondes)

BOUNDARIES_PER_SCRAPING = 20

# --- Proxy Configuration ---
# The credentials from your manager
proxy_username = 'pnuuwebv'
proxy_password = 'njqgpghsah6h'
proxy_host = '23.95.150.145'
proxy_port = 6114

# The correct way to structure the proxy settings for Playwright
CONFIG_PROXY = {
    "server": f"http://{proxy_host}:{proxy_port}",  # The server is just the host and port
    "username": proxy_username,                    # The username is a separate key
    "password": proxy_password                     # The password is a separate key
}