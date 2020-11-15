# simple_btc_algo

## Summary: Long-only 50/100 period moving average crossover

![Image](https://github.com/samchaaa/simple_btc_algo/bt.png)

Uses cbpro (from https://github.com/danpaquin/coinbasepro-python/), with minor modifications.

Just a simple long-only moving average crossover for BTC-USD on the Coinbase Pro exchange (formerly GDAX). Requests previous 100 hourly bars from the Coinbase Pro public API, then checks for a 50/100 period simple moving average crossover, once per hour.

Default size is 0.001 BTC, so the algo will by default trade just 0.001 per hour, until you are either 100% long or 100% flat.

Algorithm is set up to implement immediately, just input your credentials and run.

**Subscribe to https://samchaaa.substack.com/ for more in depth code, studies, and ready-to-implement algorithms.**
