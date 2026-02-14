#!/usr/bin/env python3
"""
Stripe Setup - Creates products and prices for CleanEstimate.

Run once with your Stripe secret key to create all products/prices,
then paste the output into your .env file.

Usage:
    python stripe_setup.py sk_test_YOUR_KEY_HERE
    python stripe_setup.py sk_live_YOUR_KEY_HERE   # for production
"""

import sys
import stripe

PLANS = [
    {
        'name': 'CleanEstimate Starter',
        'description': '5 team members, 25 active jobs, email & PDF reports',
        'price_cents': 2900,  # $29/mo
        'env_var': 'STRIPE_PRICE_STARTER',
    },
    {
        'name': 'CleanEstimate Pro',
        'description': '15 team members, 100 active jobs, AI assistant included',
        'price_cents': 7900,  # $79/mo
        'env_var': 'STRIPE_PRICE_PRO',
    },
    {
        'name': 'CleanEstimate Enterprise',
        'description': '50 team members, unlimited jobs, priority support',
        'price_cents': 14900,  # $149/mo
        'env_var': 'STRIPE_PRICE_ENTERPRISE',
    },
]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    key = sys.argv[1]
    if not key.startswith('sk_'):
        print("Error: Key must start with sk_test_ or sk_live_")
        sys.exit(1)

    stripe.api_key = key
    mode = "TEST" if "test" in key else "LIVE"
    print(f"\n  Stripe Setup ({mode} mode)")
    print(f"  {'='*40}\n")

    # Verify key works
    try:
        stripe.Account.retrieve()
        print("  Key verified.\n")
    except stripe.AuthenticationError:
        print("  Error: Invalid API key.")
        sys.exit(1)

    env_lines = [
        f"STRIPE_SECRET_KEY={key}",
    ]

    # Get publishable key hint
    pk_prefix = "pk_test_" if "test" in key else "pk_live_"
    env_lines.append(f"STRIPE_PUBLISHABLE_KEY={pk_prefix}YOUR_PUBLISHABLE_KEY_HERE")

    for plan in PLANS:
        print(f"  Creating: {plan['name']}...")

        # Create product
        product = stripe.Product.create(
            name=plan['name'],
            description=plan['description'],
        )

        # Create monthly price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=plan['price_cents'],
            currency='usd',
            recurring={'interval': 'month'},
        )

        env_lines.append(f"{plan['env_var']}={price.id}")
        print(f"    Product: {product.id}")
        print(f"    Price:   {price.id} (${plan['price_cents']/100:.0f}/mo)")
        print()

    env_lines.append("STRIPE_WEBHOOK_SECRET=whsec_SET_THIS_AFTER_CREATING_WEBHOOK")
    env_lines.append("APP_DOMAIN=http://localhost:5000")

    # Write .env file
    env_content = "\n".join(env_lines) + "\n"
    with open(".env.stripe", "w") as f:
        f.write(env_content)

    print(f"  {'='*40}")
    print(f"  Done! Saved to .env.stripe\n")
    print("  Add these to your .env file:\n")
    for line in env_lines:
        print(f"    {line}")
    print()
    print("  Next steps:")
    print("  1. Copy your publishable key from Stripe Dashboard")
    print("  2. Create a webhook endpoint in Stripe Dashboard:")
    print("     URL: https://yourdomain.com/stripe/webhook")
    print("     Events: customer.subscription.updated,")
    print("             customer.subscription.deleted,")
    print("             invoice.payment_failed")
    print("  3. Set STRIPE_WEBHOOK_SECRET from the webhook")
    print("  4. Set APP_DOMAIN to your production URL")
    print()


if __name__ == "__main__":
    main()
