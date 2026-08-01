using Xunit;
using CapstoneProject;

namespace CapstoneTests;

public class AppTests
{
    [Fact]
    public void TestLogItemPropertyAssignments()
    {
        var item = new LogItem();

        item.Letter = "V";
        item.Fingers = 2;

        Assert.Equal("V", item.Letter);
        Assert.Equal(2, item.Fingers);
    }

    [Fact]
    public void TestDataTimestampInitializes()
    {
        var item = new LogItem { Letter = "S" };

        Assert.True(item.CreatedAt <= DateTime.Now);
    }
}
