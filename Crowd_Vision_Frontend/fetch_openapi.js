
import https from 'https';

https.get('https://crowdvision-api.tride.live/openapi.json', (res) => {
    let data = '';
    res.on('data', c => data += c);
    res.on('end', () => require('fs').writeFileSync('openapi.json', data));
});
