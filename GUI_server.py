# Generative AI was used for some Code

from aiohttp import web
import socket

# Global variable to store the latest data
latest_data = {}
shutdown_requested = False

# function for the endpoints
async def handle(request):
    with open('templates/index.html', 'r') as file:
        content = file.read()
    return web.Response(text=content, content_type='text/html')


async def shutdown(request):
    global shutdown_requested
    shutdown_requested = True
    return web.Response(text='OpenCEM will shutdown soon...')


async def shutdown_requested_function(request):
    global shutdown_requested
    return web.Response(text=str(shutdown_requested))


async def update_data(request):
    global latest_data
    data = await request.json()
    latest_data = data  # Update the latest data

    return web.Response(text='Data received and updated successfully.')


async def get_latest_data(request):
    global latest_data
    return web.json_response(latest_data)


def start_GUI_server():
    app = web.Application()
    # add endpoints to web server
    app.router.add_get('/', handle)
    app.router.add_post('/update', update_data)
    app.router.add_get('/latest_data', get_latest_data)
    app.router.add_post('/shutdown', shutdown)
    app.router.add_get('/shutdown_requested', shutdown_requested_function)

    IP_address = get_local_ip() # get local ip
    host = IP_address
    port = 8000

    web.run_app(app, host=host, port=port)


def get_local_ip():
    try:
        # Create a socket object
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Use a dummy address to get the local IP address
        s.connect(("8.8.8.8", 80))

        # Get the local IP address
        local_ip = s.getsockname()[0]

        return local_ip
    except Exception as e:
        print("Error:", e)
        return None


if __name__ == "__main__":
    start_GUI_server()
