# Function to kill processes using a port
kill_port() {
    local port=$1
    echo "Checking for processes using port $port..."
    
    # Find and kill processes using the port
    pids=$(lsof -ti:$port)
    if [ ! -z "$pids" ]; then
        echo "Found processes using port $port: $pids"
        echo "Killing processes..."
        kill -9 $pids 2>/dev/null
        sleep 2
    fi
}

# Function to cleanup processes
cleanup() {
    echo "Cleaning up..."
    if [ ! -z "$API_PID" ]; then
        kill $API_PID 2>/dev/null
    fi
    if [ ! -z "$NGROK_PID" ]; then
        kill $NGROK_PID 2>/dev/null
    fi
    
    # Kill any remaining processes on ports 5000-5010
    for port in {5000..5010}; do
        pids=$(lsof -ti:$port 2>/dev/null)
        if [ ! -z "$pids" ]; then
            kill -9 $pids 2>/dev/null
        fi
    done
    
    echo "Cleanup complete."
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

echo "🚀 Starting Gujarat Smart Assistant API..."

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found. Please create it first with: python3 -m venv venv"
    exit 1
fi

# Kill any existing processes on common ports
kill_port 5000
kill_port 4040

# Wait a moment for ports to be freed
sleep 3

# Start the API (it will find its own available port)
echo "🔧 Starting API server..."
python3 api.py &
API_PID=$!

# Wait for API to initialize and find its port
sleep 8

# Try to find which port the API is using
API_PORT=""
for port in {5000..5010}; do
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        API_PORT=$port
        break
    fi
done

if [ -z "$API_PORT" ]; then
    echo "❌ Could not detect API port. Check if the API started successfully."
    echo "Checking API logs..."
    sleep 2
    cleanup
    exit 1
fi

echo "✅ API is running successfully on port $API_PORT"
echo "🌐 API URL: http://localhost:$API_PORT"

# Start Ngrok tunnel
echo "🔗 Starting Ngrok tunnel..."
ngrok http $API_PORT > ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for Ngrok to initialize
echo "⏳ Waiting for Ngrok to initialize..."
sleep 10

# Get Ngrok URL with retries
NGROK_URL=""
for attempt in {1..6}; do
    echo "🔍 Attempt $attempt: Checking Ngrok status..."
    
    # Check if ngrok is running
    if ! pgrep -f "ngrok" > /dev/null; then
        echo "❌ Ngrok process not found. Checking logs..."
        if [ -f "ngrok.log" ]; then
            echo "Last few lines of ngrok.log:"
            tail -10 ngrok.log
        fi
        break
    fi
    
    # Try to get the URL
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | jq -r '.tunnels[]?.public_url' 2>/dev/null | head -1)
    
    if [ -n "$NGROK_URL" ] && [ "$NGROK_URL" != "null" ] && [ "$NGROK_URL" != "" ]; then
        echo "✅ Ngrok tunnel established!"
        break
    fi
    
    echo "⏳ Waiting for Ngrok tunnel... (attempt $attempt/6)"
    sleep 5
done

# Display status
echo ""
echo "========================================="
echo "🎉 GUJARAT SMART ASSISTANT API STATUS"
echo "========================================="
echo "🏠 Local API:        http://localhost:$API_PORT"
echo "📋 Main Endpoint:    http://localhost:$API_PORT/smart_assistant"
echo "🏥 Health Check:     http://localhost:$API_PORT/health"
echo "🔧 Ngrok Dashboard:  http://localhost:4040"

if [ -n "$NGROK_URL" ] && [ "$NGROK_URL" != "null" ] && [ "$NGROK_URL" != "" ]; then
    echo "🌐 Public URL:       $NGROK_URL"
    echo "🚀 Public Endpoint:  $NGROK_URL/smart_assistant"
    echo ""
    echo "✅ All services are running successfully!"
else
    echo "❌ Public URL:       Failed to establish Ngrok tunnel"
    echo ""
    echo "⚠️  API is running locally, but external access failed."
    echo "   You can still test locally or check Ngrok logs."
    
    if [ -f "ngrok.log" ]; then
        echo ""
        echo "📋 Recent Ngrok logs:"
        tail -15 ngrok.log
    fi
fi

echo ""
echo "📝 Testing your API:"
echo "   curl http://localhost:$API_PORT/health"
echo ""
echo "🛑 Press Ctrl+C to stop all services"
echo "========================================="

# Keep script running and wait for API process
wait $API_PID
