## Multi-stage build for the React frontend

# Stage 1: build the application using Node.js
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* .
RUN npm install --frozen-lockfile || npm install
COPY . .
RUN npm run build

# Stage 2: serve the built static files with nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]