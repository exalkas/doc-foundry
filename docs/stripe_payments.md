Here are Stripe test card numbers you can use in test mode:

## Successful payments

### Visa (most common)

- Card number: `4242 4242 4242 4242`
- Expiry: Any future date (e.g., `12/34`)
- CVC: Any 3 digits (e.g., `123`)
- ZIP: Any 5 digits (e.g., `12345`)

### Visa (Debit)

- Card number: `4000 0566 5566 5556`

### Mastercard

- Card number: `5555 5555 5555 4444`

### American Express

- Card number: `3782 822463 10005`

## Declined payments (for testing error handling)

### Card declined (generic)

- Card number: `4000 0000 0000 0002`

### Insufficient funds

- Card number: `4000 0000 0000 9995`

### Lost card

- Card number: `4000 0000 0000 9987`

### Stolen card

- Card number: `4000 0000 0000 9979`

### Processing error

- Card number: `4000 0000 0000 0119`

## 3D Secure authentication

### Requires authentication

- Card number: `4000 0027 6000 3184`
- When using this card, you'll be prompted to authenticate

### Authentication fails

- Card number: `4000 0082 6000 3178`

## Other test scenarios

### Requires ZIP code

- Card number: `4000 0000 0000 0010`
- ZIP: `12345` (or any valid ZIP)

### Requires CVC

- Card number: `4000 0000 0000 0127`

## Important notes

1. Use any future expiry date (e.g., `12/34` or `01/25`)
2. Use any 3-digit CVC for most cards
3. Use any 5-digit ZIP code for US addresses
4. These only work in test mode (with `sk_test_...` keys)
5. No real charges are made with these cards

## Quick reference

Most common test card:

- Number: `4242 4242 4242 4242`
- Expiry: `12/34`
- CVC: `123`
- ZIP: `12345`

You can use these in your Stripe Checkout session when testing plan selection. The successful payment cards will complete the checkout flow, while the declined cards will help you test error handling in your application.
