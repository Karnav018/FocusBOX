
from src.spotify_client import SpotifyClient
from spotipy.oauth2 import SpotifyOAuth

# 1. Setup Auth Manager with same settings
client = SpotifyClient()
sp_oauth = SpotifyOAuth(
    client_id=client.client_id,
    client_secret=client.client_secret,
    redirect_uri=client.redirect_uri,
    scope="user-modify-playback-state,user-read-playback-state"
)

# 2. Exchange Code for Token
# Extract code from URL provided by user
code = "AQB-xBLy01RvWdHRmylwI1gAW-oDA9ju7CnLqD9todwtIRGMS2e1p_bKkkti3-5dlMo3BW404UE3vt3tq-ZM9h5lSI5YImhTS3kO24htp8yCdV_ROvjXiOEt1BfuE-e9W6ArlHusuMopOknFCJBKTKxGJRbr9GDU56HlCUm6gMXf6Fzkpok6v2nNGqtOGa5eYkZ_q5Bl_2wxnH6UF7JzEsenEamz2xcGa8Bdqeq0_neOS1RxNpq7UA"

try:
    token_info = sp_oauth.get_access_token(code)
    print("✅ Token Acquired & Cached!")
except Exception as e:
    print(f"❌ Auth Failed: {e}")
