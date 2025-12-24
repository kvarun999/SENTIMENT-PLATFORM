FROM node:18-alpine

WORKDIR /app

# Install dependencies first (caching)
COPY package.json .
# We will create package.json in a moment
RUN npm install

COPY . .

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "run", "dev"]
