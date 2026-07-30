using CapstoneProject;
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

List<LogItem> logs = [];
object logsLock = new();
int nextId = 1;

app.MapGet("/api/logs", () =>
{
    lock (logsLock)
    {
        return Results.Ok(logs.ToList());
    }
});

app.MapGet("/api/logs/{id:int}", (int id) =>
{
    lock (logsLock)
    {
        var log = logs.FirstOrDefault(l => l.Id == id);
        return log is null ? Results.NotFound() : Results.Ok(log);
    }
});

app.MapPost("/api/logs", ([FromBody] LogItem log) =>
{
    lock (logsLock)
    {
        log.Id = nextId++;
        log.CreatedAt = DateTime.Now;
        logs.Add(log);
        return Results.Created($"/api/logs/{log.Id}", log);
    }
});

app.MapPut("/api/logs/{id:int}", (int id, [FromBody] LogItem updatedLog) =>
{
    lock (logsLock)
    {
        var existingLog = logs.FirstOrDefault(l => l.Id == id);
        if (existingLog is null)
        {
            return Results.NotFound();
        }

        existingLog.Letter = updatedLog.Letter;
        existingLog.Fingers = updatedLog.Fingers;
        return Results.NoContent();
    }
});

app.MapDelete("/api/logs/{id:int}", (int id) =>
{
    lock (logsLock)
    {
        var log = logs.FirstOrDefault(l => l.Id == id);
        if (log is null)
        {
            return Results.NotFound();
        }

        logs.Remove(log);
        return Results.NoContent();
    }
});

app.Run();
