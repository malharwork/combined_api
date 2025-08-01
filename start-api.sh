source venv/bin/activate

echo "Starting Gujarat API..."
python3 api.py &
API_PID=$!

echo "Waiting for API to initialize..."
sleep 5

echo "Starting Ngrok tunnel..."
ngrok http 5000 > ngrok.log 2>&1 &
NGROK_PID=$!

echo "Waiting for Ngrok to initialize..."
sleep 8

NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url' 2>/dev/null)

if [ -n "$NGROK_URL" ] && [ "$NGROK_URL" != "null" ]; then
   echo "✅ Your API is now available at: $NGROK_URL"
   echo "Main endpoint: $NGROK_URL/smart_assistant"
else
   echo "❌ Failed to get Ngrok URL. Check if Ngrok is running properly."
   echo "You can manually check at http://localhost:4040"
fi

echo "API is running on http://localhost:5000"
echo "Ngrok dashboard available at http://localhost:4040"
echo "Press Ctrl+C to stop all services"

function cleanup {
   echo "Stopping services..."
   kill $API_PID 2>/dev/null
   kill $NGROK_PID 2>/dev/null
   echo "Services stopped."
   exit 0
}

trap cleanup SIGINT

wait $API_PID