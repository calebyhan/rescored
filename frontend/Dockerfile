FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy application code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Default command
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
