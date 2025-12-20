document.addEventListener("DOMContentLoaded", function() {

    // Pre-upload processing options
    // Get the checkbox and the content div by their IDs
    var IDcheckbox = document.getElementById("split_ids");
    var IDoptions = document.getElementById("splitId_options");

    IDcheckbox.addEventListener("change", function() {
        if (IDcheckbox.checked) {
            IDoptions.style.display = "block";
        } else {
            IDoptions.style.display = "none";
        }
    });

    var flowcheckbox = document.getElementById("flowjo");
    var flowoptions = document.getElementById("FlowJo_option");

    flowcheckbox.addEventListener("change", function() {
        if (flowcheckbox.checked) {
            flowoptions.style.display = "block";
        } else {
            flowoptions.style.display = "none";
        }
    });

    // Get all elements
    const leftValues = document.getElementById('leftValues_Cat');
    const centerValues = document.getElementById('centerValues');
    const rightValues = document.getElementById('rightValues_Con');

    const btnLeftCat = document.getElementById('btnLeft_Cat');
    const btnRight = document.getElementById('btnRight');
    const btnLeft = document.getElementById('btnLeft');
    const btnRightCon = document.getElementById('btnRight_Con');
    const submitBtn = document.getElementById('columns');

    // Move selected items from center to left (Categorical)
    btnRight.addEventListener('click', function() {
        moveOptions(leftValues, centerValues);
    });

    // Move selected items from left to center
    btnLeftCat.addEventListener('click', function() {
        moveOptions(centerValues, leftValues);
    });

    // Move selected items from center to right (Continuous)
    btnRightCon.addEventListener('click', function() {
        moveOptions(centerValues, rightValues);
    });

    // Move selected items from right to center
    btnLeft.addEventListener('click', function() {
        moveOptions(rightValues, centerValues);
    });

    // Function to move options between selects
    function moveOptions(fromSelect, toSelect) {
        const selectedOptions = Array.from(fromSelect.selectedOptions);
        
        selectedOptions.forEach(option => {
            // Preserve the title attribute when moving
            const newOption = option.cloneNode(true);
            if (!newOption.hasAttribute('title')) {
                newOption.setAttribute('title', option.textContent);
            }
            toSelect.appendChild(newOption);
            option.remove();
        });
    }

    // Submit handler
    submitBtn.addEventListener('click', function() {
        const categorical = Array.from(leftValues.options).map(opt => opt.value);
        const continuous = Array.from(rightValues.options).map(opt => opt.value);
        
        if (categorical.length === 0 || continuous.length === 0) {
        alert('Please select at least one categorical and one continous variable');
        return;
        }

        // Create object with both lists
        const data = {
            categorical: categorical,
            continuous: continuous
        };
        
        console.log('Categorical Variables:', categorical);
        console.log('Continuous Variables:', continuous);
        console.log('Sending data:', data);
        
        // Send data to Flask endpoint using the fetch API
        fetch('/process_columns', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            console.log('Success:', data);
            window.location.replace('/graph');
        })
        .catch((error) => {
            console.error('Error:', error);
            alert('Error: ' + error.message);
        });
    }); 


    document.getElementById("result").textContent = "JavaScript is working!";
});


