from django.db import models

class Project(models.Model):
    """The main container for the entire project, starting with the vision."""
    name = models.CharField(max_length=255)
    vision = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Outcome(models.Model):
    """A desired outcome of the project. A project can have many outcomes."""
    project = models.ForeignKey(Project, related_name='outcomes', on_delete=models.CASCADE)
    description = models.TextField()

class Benefit(models.Model):
    """A specific benefit achieved from an outcome. A project can have many benefits."""
    project = models.ForeignKey(Project, related_name='benefits', on_delete=models.CASCADE)
    description = models.TextField()

class Deliverable(models.Model):
    """A tangible item produced to realize benefits. A project can have many deliverables."""
    project = models.ForeignKey(Project, related_name='deliverables', on_delete=models.CASCADE)
    description = models.TextField()

class Task(models.Model):
    """A specific task required to create a deliverable. A deliverable has many tasks."""
    # This links a task to a specific deliverable.
    deliverable = models.ForeignKey(Deliverable, related_name='tasks', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    progress = models.IntegerField(default=0)