import https from 'https';

const url = 'https://crowdvision-api.tride.live/api/alerts?hours=24&limit=5';

https.get(url, (res) => {
    let data = '';

    console.log('Status Code:', res.statusCode);

    res.on('data', (chunk) => {
        data += chunk;
    });

    res.on('end', () => {
        try {
            if (res.statusCode === 200) {
                const json = JSON.parse(data);
                console.log('API Response Structure:', JSON.stringify(json, null, 2));
                if (json.alerts && json.alerts.length > 0) {
                    console.log('Sample Alert Severity:', json.alerts[0].severity);
                } else {
                    console.log('No alerts found in response.');
                }
            } else {
                console.log('API Error Body:', data);
            }
        } catch (e) {
            console.error('Error parsing JSON:', e.message);
            console.log('Raw Data:', data);
        }
    });

}).on("error", (err) => {
    console.log("Error: " + err.message);
});
