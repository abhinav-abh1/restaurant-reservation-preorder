let selectedItems = [];

function filterCategory(category) {
  document.querySelectorAll(".menu-card").forEach(card => {
    if (category === "All" || card.dataset.category === category) {
      card.style.display = "block";
    } else {
      card.style.display = "none";
    }
  });
}

function addItem(id, name, price) {
  const exists = selectedItems.find(i => i.id === id);
  if (exists) return;

  selectedItems.push({ id, name, price });
  renderSelected();
}

function renderSelected() {
  const list = document.getElementById("selectedList");
  list.innerHTML = "";

  selectedItems.forEach(i => {
    const li = document.createElement("li");
    li.innerText = `${i.name} – ₹${i.price}`;
    list.appendChild(li);
  });
}

function submitItems() {
  if (selectedItems.length === 0) {
    alert("Select at least one item");
    return false;
  }
  document.getElementById("itemsInput").value =
    JSON.stringify(selectedItems);
  return true;
}
