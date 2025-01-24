elems = {
    videos: document.getElementById('videos'),
    schedule: document.getElementById('schedule')
}

tick = `<svg class="tick" width="11" height="10" viewBox="0 0 11 10" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2 4.5L3.73167 7.61701C4.08842 8.25915 4.9926 8.31036 5.41957 7.71261L9.5 2" stroke="black" stroke-width="3" stroke-linecap="round"/></svg> `

async function getDb() {
    fetch('db.json')
    .then((res) => res.json())
    .then((data) => {
        elems.videos.innerHTML = ''
        videos = data.videos
        Object.entries(videos).reverse().forEach(([key, entry]) => {
            element = `
                <div class="card ${(entry.status == 'ready' ? '' : 'disabled')}" onclick="watch('${entry.file}', '${key.slice(5)}', '${key.episode}'">
                    <img class="cover" src="${entry.cover}">
                    <div class="shadow"></div>
                    <div class="content">
                        <div class="labels">
                            <p class="label">${(entry.watched != null ? tick : '')}EP ${entry.episode}</p>
                            <p class="label secondary ${(entry.status == 'ready' ? 'hidden' : '')}">${entry.status}</p>
                        </div>
                        <p class="title">${key.slice(5).replaceAll('<', '&lt;')}</p>
                    </div>
                </div>
            `
            elems.videos.innerHTML += element
        })
    })
}

function watch(file, title) {
    if (file == 'null') {
        return
    }
    localStorage.setItem('file', file)
    localStorage.setItem('title', title)
    localStorage.setItem('episode', episode)
    location.href = '/watch.html'
}

getDb()
setInterval(getDb, 5000)
