fetch(`${window.location.origin}/api/redirect`)
    .then((res) => res.json())
    .then((data) => {
        url = `https://anilist.co/api/v2/oauth/authorize?client_id=${data.cid}&redirect_uri=${data.redirect}/api/auth&response_type=code`
        document.getElementById('anilist').setAttribute('href', url)
    })

inputs = document.getElementById('inputs')

function mainForm() {
    inputs.innerHTML = `
        <a class="button" id="anilist">
             <svg id="aniListIcon" width="361" height="273" viewBox="0 0 361 273" fill="none" xmlns="http://www.w3.org/2000/svg">
                 <path d="M246.921 203.272V16.602C246.921 5.90401 241.034 0 230.363 0H193.93C183.258 0 177.369 5.90401 177.369 16.602V105.253C177.369 107.75 201.365 119.342 201.992 121.794C220.274 193.404 205.964 250.714 188.633 253.394C216.97 254.799 220.088 268.458 198.981 259.125C202.21 220.916 214.809 220.991 251.03 257.719C251.34 258.036 258.457 273.001 258.9 273.001H344.445C355.117 273.001 361.003 267.101 361.003 256.401V219.877C361.003 209.179 355.117 203.275 344.445 203.275L246.921 203.272Z" fill="#02A9FF"/>
                 <path d="M95.681 0.00195312L0 273.002H74.338L90.53 225.78H171.49L187.316 273.002H261.284L165.97 0.00195312H95.681ZM107.457 165.282L130.64 89.653L156.033 165.282H107.457Z" fill="#FEFEFE"/>
             </svg>
             AniList
         </a>
         <button class="button" id="guest" onclick="guestForm()">
             Guest
         </button>
    `
}

function guestForm() {
    inputs.innerHTML = `
        <button class="button" id="guest" onclick="mainForm()">
             Back
        </button>
        <div class="separator"></div>
        <input class="input" type="password" id="password" placeholder="Guest password">
        <button class="button" id="guest" onclick="guestLogin()">
             Login
        </button>
    `
}