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
{   // Assings a unique ID and timestamp to the new log item, then adds it to the list
    lock (logsLock)
    {
        log.Id = nextId++;
        log.CreatedAt = DateTime.Now; // logs timestamps 
        logs.Add(log);
        return Results.Created($"/api/logs/{log.Id}", log);
    }
});
    // PUT endpoint to update an existing log item
app.MapPut("/api/logs/{id:int}", (int id, [FromBody] LogItem updatedLog) =>
{
    lock (logsLock)
    {
        var existingLog = logs.FirstOrDefault(l => l.Id == id);
        if (existingLog is null)
        {
            return Results.NotFound();
        }
        // Update the properties of the existing log item  
        existingLog.Letter = updatedLog.Letter;
        existingLog.Fingers = updatedLog.Fingers;
        return Results.NoContent();
    }
});
    // Deletes a log item by its ID
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
