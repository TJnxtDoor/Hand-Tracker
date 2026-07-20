using System;

namespace CapstoneProject;

public class LogItem
{
    public int Id { get; set; }
    public string Letter { get; set; } = "";
    public int Fingers { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.Now;
}
