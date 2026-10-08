
import https from 'https';

https.get('http://localhost:6006/openapi.json', (res) => {
    let data = '';
    res.on('data', c => data += c);
    res.on('end', () => require('fs').writeFileSync('openapi.json', data));
});
