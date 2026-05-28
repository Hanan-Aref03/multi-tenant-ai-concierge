# Ali Faddel owns the widget runtime image.
FROM node:20-alpine AS build

WORKDIR /widget

COPY package*.json ./
RUN npm ci

COPY . ./
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY --from=build /widget/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
