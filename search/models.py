from django.db import models

class Article(models.Model):
    pmid = models.CharField(max_length=32, unique=True)
    title = models.TextField()
    authors = models.TextField()
    journal = models.CharField(max_length=255)
    year = models.IntegerField()
    quality = models.CharField(max_length=10)
    study_type = models.CharField(max_length=100)
    sample_size = models.IntegerField(default=0)
    region = models.CharField(max_length=100, blank=True)
    abstract = models.TextField(blank=True)

    def __str__(self):
        return f"{self.title[:60]}..."
