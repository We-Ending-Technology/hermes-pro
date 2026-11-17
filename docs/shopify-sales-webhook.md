# Shopify sales webhooks

The Hermes API receives only the financial events listed below. The Shopify connector inside ChatGPT is separate from the Hermes backend; connecting one does not automatically register webhooks for the other.

## Render environment

Set these variables on the `hermes-pro-api-commercial` service:

- `SHOPIFY_STORE_DOMAIN=0200rp-kz.myshopify.com`
- `SHOPIFY_WEBHOOK_SECRET`: the client secret of the Shopify app that owns the webhook subscriptions. Treat this value like a password. Do not commit it or paste it into chat.

## Webhook destination

`https://hermes-pro-api-commercial.onrender.com/api/v1/webhooks/shopify`

Register these HTTPS subscriptions, with JSON payloads:

- `orders/paid`
- `refunds/create`

The endpoint verifies the `X-Shopify-Hmac-Sha256` signature against the raw request body, checks `X-Shopify-Shop-Domain`, and stores only order/refund IDs, amount, currency, and timestamps. Customer email, phone, address, and customer objects are not stored.

The endpoint does not create Shopify products, attach digital files, publish products, or activate the store's checkout. Those remain separate steps.
