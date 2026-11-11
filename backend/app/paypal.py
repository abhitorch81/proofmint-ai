from decimal import Decimal
import httpx
from fastapi import HTTPException
from .config import get_settings

class PayPalClient:
    def __init__(self):
        self.settings = get_settings()
        if not self.settings.paypal_base_url.startswith('https://api-m.sandbox.paypal.com'):
            raise HTTPException(500, 'Phase 1 allows PayPal sandbox only')
        if not self.settings.paypal_client_id or not self.settings.paypal_client_secret:
            raise HTTPException(503, 'Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in backend/.env')

    async def _token(self, client):
        r = await client.post('/v1/oauth2/token', auth=(self.settings.paypal_client_id,self.settings.paypal_client_secret), data={'grant_type':'client_credentials'})
        self._check(r)
        return r.json()['access_token']

    @staticmethod
    def _check(r):
        if r.status_code >= 400:
            raise HTTPException(502, f'PayPal sandbox request failed (HTTP {r.status_code})')

    async def create_order(self, asset, request_id):
        async with httpx.AsyncClient(base_url=self.settings.paypal_base_url,timeout=20) as client:
            token = await self._token(client)
            body = {'intent':'CAPTURE','purchase_units':[{'reference_id':asset.id,'custom_id':asset.id,'description':asset.title[:127],'amount':{'currency_code':'USD','value':f'{Decimal(asset.price_cents)/100:.2f}'}}],
                    'application_context': {'return_url':f'{self.settings.frontend_url}/checkout/return','cancel_url':f'{self.settings.frontend_url}/?cancelled=1','user_action':'PAY_NOW'}}
            r = await client.post('/v2/checkout/orders',json=body,headers={'Authorization':f'Bearer {token}','PayPal-Request-Id':request_id,'Content-Type':'application/json'})
            self._check(r)
            return r.json()

    async def capture_order(self, order_id, request_id):
        async with httpx.AsyncClient(base_url=self.settings.paypal_base_url,timeout=20) as client:
            token=await self._token(client)
            r=await client.post(f'/v2/checkout/orders/{order_id}/capture',headers={'Authorization':f'Bearer {token}','PayPal-Request-Id':request_id,'Content-Type':'application/json'},json={})
            self._check(r)
            return r.json()

    async def get_order(self, order_id):
        async with httpx.AsyncClient(base_url=self.settings.paypal_base_url,timeout=20) as client:
            token=await self._token(client)
            r=await client.get(f'/v2/checkout/orders/{order_id}',headers={'Authorization':f'Bearer {token}'})
            self._check(r)
            return r.json()
