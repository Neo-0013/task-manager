// Custom JavaScript for Task Manager
// Add any interactive features here
document.addEventListener("DOMContentLoaded", function () {
    const deleteModal = new bootstrap.Modal(
        document.getElementById("deleteModal")
    );

    const deleteForm = document.getElementById("deleteForm");

    document.querySelectorAll(".delete-btn").forEach(btn => {
        btn.addEventListener("click", function () {
            const taskId = this.dataset.taskId;
            deleteForm.action = `/delete_task/${taskId}`;
            deleteModal.show();
        });
    });
});