const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const path = require('path');
const fs = require('fs');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);

let photocellData = [];
let masterData = {};

app.use(express.static(path.join(__dirname)));

io.on('connection', (socket) => {
    console.log('A user connected');

    socket.on('getLogFiles', () => {
        const logsDir = path.join(__dirname, 'logs');
        fs.readdir(logsDir, (err, files) => {
            if (err) {
                console.error('Error reading logs directory:', err);
                socket.emit('logFiles', []);
            } else {
                const logFiles = files.filter(file => file.endsWith('.txt'));
                socket.emit('logFiles', logFiles);
            }
        });
    });

    socket.on('getLogFileData', (logFile) => {
        const filePath = path.join(__dirname, 'logs', logFile);
        fs.readFile(filePath, 'utf8', (err, data) => {
            if (err) {
                console.error('Error reading log file:', err);
                socket.emit('logFileError', 'Error reading the log file.');
            } else {
                const parsedData = JSON.parse(data);
                photocellData = parsedData.photocellData;
                masterData = parsedData.masterData;
                console.log("parsedData", parsedData)
                // Construct graph data
                const photocellGraph = {
                    data: [{
                        x: [...Array(photocellData.length).keys()],
                        y: photocellData,
                        label: 'Photocell Data',
                    }],
                    options: {}
                };

                const masterGraph = {
                    data: {
                        labels: Object.keys(masterData),
                        datasets: [{
                            label: 'Master Active Time',
                            data: Object.values(masterData)
                        }]
                    },
                    options: {}
                };
                console.log("from log", photocellGraph)
                io.emit('updateGraphsFromFile', { photocellGraph, masterGraph });
            }
        });
    });

    socket.on('updatePhotocellData', (data) => {
        console.log(data);
        photocellData = data.photocellData;
        masterData = data.masterData;
        updateGraphs();
    });

    socket.on('resetCharts', () => {
        console.log('Received resetCharts event. Resetting charts on frontend.');

        // Save the most recent photocellData and masterData to a text file
        saveDataToFile();

        // Broadcast the resetCharts event to all clients
        io.emit('resetCharts');
    });

});


function saveDataToFile() {
    const logsDir = path.join(__dirname, 'logs');

    // Check if 'logs' directory exists, if not, create it
    if (!fs.existsSync(logsDir)) {
        fs.mkdirSync(logsDir);
    }

    // Define the file path inside the "logs" folder
    const filePath = path.join(logsDir, `chart_data_${new Date().toISOString()}.txt`);

    // Create the data to be saved
    const dataToSave = {
        timestamp: new Date().toISOString(),
        photocellData,
        masterData
    };

    // Convert the data to a string format
    const dataString = JSON.stringify(dataToSave, null, 2);

    // Write data to the file inside the "logs" folder
    fs.writeFile(filePath, dataString, (err) => {
        if (err) {
            console.error('Error writing to file:', err);
        } else {
            console.log('Data saved to', filePath);
        }
    });
}
function updateGraphs() {
    // Prepare the photocell graph data
    const photocellGraph = {
        data: [
            {
                x: photocellData.map((_, index) => index),  // Use index as the x-axis value (time)
                y: photocellData,
                label: 'Photocell Data',
                fill: false,
                borderColor: 'rgba(75, 192, 192, 1)',
                tension: 0.1
            }
        ],
        options: {
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    title: {
                        display: true,
                        text: 'Time (s)'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Photocell Value'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Photocell Data Over Time'
                }
            }
        }
    };

    // Prepare master graph data
    const masterGraph = {
        data: {
            labels: Object.keys(masterData),  // Device IPs as x-axis labels
            datasets: [
                {
                    label: 'Master Active Time',
                    data: Object.values(masterData),  // Active time as y-axis data
                    backgroundColor: 'rgba(153, 102, 255, 0.2)',
                    borderColor: 'rgba(153, 102, 255, 1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Master Device IP'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Active Time (s)'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Master Active Time'
                }
            }
        }
    };

    // Emit graph updates
    io.emit('updateGraphs', { photocellGraph, masterGraph });
}

server.listen(3000, () => {
    console.log('Server is running on port 3000');
});
