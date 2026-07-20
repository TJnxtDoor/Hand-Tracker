using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading.Tasks;
using OpenCvSharp;
using CapstoneProject;

namespace CapstoneClient;

class Program
{
    static readonly HttpClient http = new() { BaseAddress = new Uri("http://localhost:5000/") };
    static string lastLetter = "";
    static DateTime lastSaved = DateTime.MinValue;

    static async Task Main(string[] args)
    {
        while (true)
        {
            Console.Clear();
            Console.WriteLine("=== SIGN LANGUAGE CAPSTONE MENU ===");
            Console.WriteLine("1. Open Webcam Tracker (Create)");
            Console.WriteLine("2. View All Logged Letters (Read)");
            Console.WriteLine("3. Fix a Logged Letter (Update)");
            Console.WriteLine("4. Remove a Logged Letter (Delete)");
            Console.WriteLine("5. Exit");
            Console.Write("\nChoose an option: ");
            
            string choice = Console.ReadLine() ?? "";

            if (choice == "1") await RunWebcam();
            else if (choice == "2") await ViewLogs();
            else if (choice == "3") await UpdateLog();
            else if (choice == "4") await DeleteLog();
            else if (choice == "5") break;
            
            if (choice != "1")
            {
                Console.WriteLine("\nPress Enter to return to menu...");
                Console.ReadLine();
            }
        }
    }

    // CREATE: Webcam Tracking Loop
    static async Task RunWebcam()
    {
        using var capture = new VideoCapture(0);
        if (!capture.IsOpened())
        {
            Console.WriteLine("Could not open webcam. Press Enter to go back.");
            Console.ReadLine();
            return;
        }

        using var window = new Window("Webcam Tracking (Press Any Key to Close)");
        using var frame = new Mat();

        Console.WriteLine("\nWebcam running! Point your hand at the camera.");

        while (true)
        {
            capture.Read(frame);
            if (frame.Empty()) break;

            // Convert to grayscale and blur out noise
            using var gray = new Mat();
            Cv2.CvtColor(frame, gray, ColorConversionCodes.BGR2GRAY);
            Cv2.GaussianBlur(gray, gray, new Size(21, 21), 0);

            // Turn into binary black and white image
            using var thresh = new Mat();
            Cv2.Threshold(gray, thresh, 80, 255, ThresholdTypes.BinaryInv | ThresholdTypes.Otsu);

            // Find outline shapes
            Cv2.FindContours(thresh, out Point[][] contours, out _, RetrievalModes.External, ContourApproximationModes.ApproxSimple);

            if (contours.Length > 0)
            {
                // Grab the biggest shape on screen (the hand)
                int bestIdx = 0;
                double biggestArea = 0;
                for (int i = 0; i < contours.Length; i++)
                {
                    double area = Cv2.ContourArea(contours[i]);
                    if (area > biggestArea)
                    {
                        biggestArea = area;
                        bestIdx = i;
                    }
                }

                // Make sure it's big enough to not be background noise
                if (biggestArea > 5000)
                {
                    Point[] hand = contours[bestIdx];
                    Cv2.DrawContours(frame, new Point[][] { hand }, -1, Scalar.Green, 2);

                    // Quick finger calculation based on outline points
                    int[] hull = Cv2.ConvexHullIndices(hand);
                    int count = 0;
                    if (hull.Length > 5) count = 5;
                    else if (hull.Length == 2) count = 2;
                    else if (hull.Length == 1) count = 1;

                    string letter = count switch
                    {
                        5 => "B", // Open Palm
                        2 => "V", // Peace Sign
                        1 => "D", // Pointing up
                        0 => "S", // Fist
                        _ => "Unknown"
                    };

                    Cv2.PutText(frame, $"Letter: {letter}", new Point(20, 50), HersheyFonts.HersheySimplex, 1.0, Scalar.Red, 2);

                    // Throttle API sends to every 3 seconds so it doesn't spam
                    if (letter != "Unknown" && letter != lastLetter && (DateTime.Now - lastSaved).TotalSeconds > 3)
                    {
                        try
                        {
                            var newItem = new LogItem { Letter = letter, Fingers = count };
                            await http.PostAsJsonAsync("api/logs", newItem);
                            Console.WriteLine($"[Saved to API]: Detected '{letter}'");
                            lastLetter = letter;
                            lastSaved = DateTime.Now;
                        }
                        catch
                        {
                            Console.WriteLine("[Error] API server offline.");
                        }
                    }
                }
            }

            window.ShowImage(frame);
            if (Cv2.WaitKey(1) >= 0) break; // Close window on keypress
        }
    }

    // READ
    static async Task ViewLogs()
    {
        try
        {
            var logs = await http.GetFromJsonAsync<LogItem[]>("api/logs");
            if (logs == null || logs.Length == 0)
            {
                Console.WriteLine("\nNo records found in the API memory.");
                return;
            }

            Console.WriteLine("\nSaved Logs:");
            foreach (var log in logs)
            {
                Console.WriteLine($"ID: {log.Id} | Letter: {log.Letter} | Fingers: {log.Fingers} | Time: {log.CreatedAt.ToShortTimeString()}");
            }
        }
        catch
        {
            Console.WriteLine("\nFailed to connect to API.");
        }
    }

    // UPDATE
    static async Task UpdateLog()
    {
        await ViewLogs();
        Console.Write("\nEnter the ID of the log you want to fix: ");
        if (!int.TryParse(Console.ReadLine(), out int id)) return;

        Console.Write("Enter the correct letter: ");
        string newLetter = Console.ReadLine() ?? "";

        var updated = new LogItem { Letter = newLetter.ToUpper(), Fingers = 0 };
        
        try
        {
            var res = await http.PutAsJsonAsync($"api/logs/{id}", updated);
            if (res.IsSuccessStatusCode) Console.WriteLine("Log successfully updated!");
            else Console.WriteLine("Log ID not found.");
        }
        catch
        {
            Console.WriteLine("API update request failed.");
        }
    }

    // DELETE
    static async Task DeleteLog()
    {
        await ViewLogs();
        Console.Write("\nEnter the ID of the log to delete: ");
        if (!int.TryParse(Console.ReadLine(), out int id)) return;

        try
        {
            var res = await http.DeleteAsync($"api/logs/{id}");
            if (res.IsSuccessStatusCode) Console.WriteLine("Log successfully removed!");
            else Console.WriteLine("Log ID not found.");
        }
        catch
        {
            Console.WriteLine("API delete request failed.");
        }
    }
}